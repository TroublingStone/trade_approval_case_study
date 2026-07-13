import json
import sqlite3
import weakref
from collections.abc import Callable, Mapping
from dataclasses import fields
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trade_approval_core.enums import Currency, Direction, Style
from trade_approval_core.errors import ConcurrentModificationError, CorruptEventLogError, TradeNotFoundError
from trade_approval_core.events import Approved, Booked, Cancelled, Event, SentToExecute, Submitted, Updated
from trade_approval_core.trade import Trade
from trade_approval_core.trade_details import TradeDetails
from trade_approval_core.types import TradeId, UserId

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    trade_id  TEXT    NOT NULL,
    seq       INTEGER NOT NULL,
    action    TEXT    NOT NULL,
    user_id   TEXT    NOT NULL,
    timestamp TEXT    NOT NULL,
    payload   TEXT    NOT NULL,
    PRIMARY KEY (trade_id, seq)
)
"""

_ENCODERS: dict[str, Callable[[Any], Any]] = {
    "direction": lambda v: v.value,
    "style": lambda v: v.value,
    "notional_currency": lambda v: v.value,
    "notional_amount": str,
    "underlying": lambda v: [c.value for c in v],
    "trade_date": lambda v: v.isoformat(),
    "value_date": lambda v: v.isoformat(),
    "delivery_date": lambda v: v.isoformat(),
    "strike_rate": lambda v: str(v) if v is not None else None,
}
_DECODERS: dict[str, Callable[[Any], Any]] = {
    "direction": Direction,
    "style": Style,
    "notional_currency": Currency,
    "notional_amount": Decimal,
    "underlying": lambda v: (Currency(v[0]), Currency(v[1])),
    "trade_date": date.fromisoformat,
    "value_date": date.fromisoformat,
    "delivery_date": date.fromisoformat,
    "strike_rate": lambda v: Decimal(v) if v is not None else None,
}


def _encode_field(name: str, value: Any) -> Any:
    encoder = _ENCODERS.get(name)
    return encoder(value) if encoder is not None else value


def _decode_field(name: str, value: Any) -> Any:
    decoder = _DECODERS.get(name)
    return decoder(value) if decoder is not None else value


def _encode_details(details: TradeDetails) -> dict[str, Any]:
    return {f.name: _encode_field(f.name, getattr(details, f.name)) for f in fields(TradeDetails)}


def _decode_details_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {name: _decode_field(name, value) for name, value in payload.items()}


# Payload encoding/decoding per event type. Events absent from _PAYLOAD_ENCODERS
# carry no payload; an action absent from _EVENT_DECODERS is a corrupt log.
_PAYLOAD_ENCODERS: dict[type[Event], Callable[[Any], dict[str, Any]]] = {
    Submitted: lambda e: _encode_details(e.details),
    Updated: lambda e: {name: _encode_field(name, value) for name, value in e.changes.items()},
    Booked: lambda e: {
        "strike_rate": _encode_field("strike_rate", e.strike_rate),
        "confirmation": e.confirmation,
    },
}
_EVENT_DECODERS: dict[str, tuple[Callable[..., Event], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    Submitted.action: (Submitted, lambda p: {"details": TradeDetails(**_decode_details_fields(p))}),
    Approved.action: (Approved, lambda p: {}),
    Updated.action: (Updated, lambda p: {"changes": _decode_details_fields(p)}),
    Cancelled.action: (Cancelled, lambda p: {}),
    SentToExecute.action: (SentToExecute, lambda p: {}),
    Booked.action: (Booked, lambda p: {
        "strike_rate": _decode_field("strike_rate", p["strike_rate"]),
        "confirmation": p["confirmation"],
    }),
}


def _encode_payload(event: Event) -> str:
    encoder = _PAYLOAD_ENCODERS.get(type(event))
    return json.dumps(encoder(event) if encoder is not None else {})


def _decode_event(row: sqlite3.Row) -> Event:
    entry = _EVENT_DECODERS.get(row["action"])
    if entry is None:
        raise CorruptEventLogError(TradeId(row["trade_id"]))
    event_type, payload_kwargs = entry
    return event_type(
        seq=row["seq"],
        user_id=UserId(row["user_id"]),
        timestamp=datetime.fromisoformat(row["timestamp"]),
        **payload_kwargs(json.loads(row["payload"])),
    )


class SqliteTradeStore:
    """SQLite-backed TradeStore adapter: each Trade's event log is rows in a
    single append-only `events` table, keyed by (trade_id, seq).

    This is the infrastructure implementation of trade_approval_core's
    TradeStore Protocol -- it lives in the API layer and depends only on the
    core library's public surface (events, TradeDetails, Trade.from_events).

    Intended for a single connection used from one thread (e.g. the asyncio
    event loop thread serving `async def` FastAPI routes that never await
    between load/save) -- there is no internal locking.
    """

    def __init__(self, path: str | Path) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        self._known_counts: weakref.WeakKeyDictionary[Trade, int] = weakref.WeakKeyDictionary()

    def close(self) -> None:
        self._conn.close()

    def save(self, trade: Trade) -> None:
        events = trade.events
        base = self._known_counts.get(trade, 0)
        new_events = events[base:]
        if not new_events:
            return
        rows = [
            (trade.id, e.seq, e.action, e.user_id, e.timestamp.isoformat(), _encode_payload(e))
            for e in new_events
        ]
        try:
            with self._conn:
                self._conn.executemany(
                    "INSERT INTO events (trade_id, seq, action, user_id, timestamp, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    rows,
                )
        except sqlite3.IntegrityError as exc:
            raise ConcurrentModificationError(trade.id) from exc
        self._known_counts[trade] = len(events)

    def get(self, trade_id: TradeId) -> Trade:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE trade_id = ? ORDER BY seq ASC", (trade_id,)
        ).fetchall()
        if not rows:
            raise TradeNotFoundError(trade_id)
        trade = Trade.from_events(trade_id, (_decode_event(row) for row in rows))
        self._known_counts[trade] = len(rows)
        return trade

    def list(self, *, limit: int | None = None, after: TradeId | None = None) -> list[Trade]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE trade_id IN ("
            "  SELECT DISTINCT trade_id FROM events WHERE trade_id > ? ORDER BY trade_id LIMIT ?"
            ") ORDER BY trade_id ASC, seq ASC",
            (after if after is not None else "", limit if limit is not None else -1),
        ).fetchall()
        grouped: dict[TradeId, list[Event]] = {}
        for row in rows:
            trade_id = TradeId(row["trade_id"])
            grouped.setdefault(trade_id, []).append(_decode_event(row))
        trades = [Trade.from_events(trade_id, events) for trade_id, events in grouped.items()]
        for trade in trades:
            self._known_counts[trade] = len(trade.events)
        return trades
