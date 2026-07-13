from decimal import Decimal

import pytest
from trade_approval_core.enums import State
from trade_approval_core.errors import ConcurrentModificationError, TradeNotFoundError
from trade_approval_core.trade import Trade
from trade_approval_core.types import TradeId

from trade_approval_api.sqlite_store import SqliteTradeStore


class TestRoundTrip:
    """Every event type must survive a save/get cycle with values intact --
    Decimal, date, enum, and tuple fields don't round-trip through JSON as-is,
    so this exercises the store's (de)serialization, not just its bookkeeping.
    """

    def test_submitted_details_round_trip_exactly(self, fake_clock, make_trade_details, user1, tmp_path):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade = Trade(clock=fake_clock)
        original = make_trade_details()
        trade.submit(user1, original)
        store.save(trade)

        reloaded = store.get(trade.id)
        assert reloaded.details == original
        assert reloaded.details.strike_rate is None
        assert reloaded.state == State.PENDING_APPROVAL
        assert reloaded.requester == user1

    def test_full_lifecycle_round_trips_every_event_type(
        self, fake_clock, make_trade_details, user1, user2, tmp_path
    ):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.update(user2, make_trade_details(notional_amount=Decimal("1200000")))
        trade.accept(user1)
        trade.send_to_execute(user2)
        trade.book(user1, Decimal("1.2345"), confirmation="CONF-1")
        store.save(trade)

        reloaded = store.get(trade.id)
        assert reloaded.state == State.EXECUTED
        assert reloaded.details.notional_amount == Decimal("1200000")
        assert reloaded.details.strike_rate == Decimal("1.2345")
        assert [record.action for record in reloaded.history()] == [
            "Submit",
            "Update",
            "Approve",
            "SendToExecute",
            "Book",
        ]
        assert reloaded.diff(0, 1) == {"notional_amount": (Decimal("1000000"), Decimal("1200000"))}


class TestDurabilityAcrossInstances:
    def test_trade_persists_across_separate_store_instances_on_same_file(
        self, fake_clock, make_trade_details, user1, tmp_path
    ):
        db_path = tmp_path / "trades.db"
        original = make_trade_details()

        store1 = SqliteTradeStore(db_path)
        trade = Trade(clock=fake_clock)
        trade.submit(user1, original)
        store1.save(trade)
        store1.close()

        store2 = SqliteTradeStore(db_path)
        reloaded = store2.get(trade.id)
        assert reloaded.details == original
        assert reloaded.state == State.PENDING_APPROVAL
        store2.close()


class TestNotFound:
    def test_get_unknown_trade_id_raises_not_found(self, tmp_path):
        store = SqliteTradeStore(tmp_path / "trades.db")
        missing_id = TradeId("does-not-exist")

        with pytest.raises(TradeNotFoundError) as exc_info:
            store.get(missing_id)
        assert exc_info.value.trade_id == missing_id


class TestAppendOnlySave:
    def test_saving_same_object_twice_does_not_duplicate_events(
        self, fake_clock, make_trade_details, user1, tmp_path
    ):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())

        store.save(trade)
        store.save(trade)

        assert len(store.get(trade.id).history()) == 1

    def test_saving_after_further_actions_only_appends_new_events(
        self, fake_clock, make_trade_details, user1, user2, tmp_path
    ):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        store.save(trade)

        trade.accept(user2)
        store.save(trade)

        assert [r.action for r in store.get(trade.id).history()] == ["Submit", "Approve"]


class TestConcurrentModification:
    def test_two_independently_loaded_copies_conflict_on_second_save(
        self, fake_clock, make_trade_details, user1, tmp_path
    ):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        store.save(trade)

        stale = store.get(trade.id)
        fresh = store.get(trade.id)
        stale.cancel(user1)
        fresh.cancel(user1)

        store.save(stale)
        with pytest.raises(ConcurrentModificationError) as exc_info:
            store.save(fresh)
        assert exc_info.value.trade_id == trade.id
        assert store.get(trade.id).state == State.CANCELLED
        assert len(store.get(trade.id).history()) == 2

    def test_saving_the_same_object_again_after_a_conflict_is_not_itself_a_conflict(
        self, fake_clock, make_trade_details, user1, tmp_path
    ):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        store.save(trade)

        stale = store.get(trade.id)
        fresh = store.get(trade.id)
        stale.cancel(user1)
        store.save(stale)

        fresh.cancel(user1)
        with pytest.raises(ConcurrentModificationError):
            store.save(fresh)

        store.save(stale)


class TestList:
    def test_list_on_empty_store_is_empty(self, tmp_path):
        store = SqliteTradeStore(tmp_path / "trades.db")
        assert store.list() == []

    def test_list_reflects_all_saved_trades(self, fake_clock, make_trade_details, user1, tmp_path):
        store = SqliteTradeStore(tmp_path / "trades.db")
        trade_a = Trade(clock=fake_clock)
        trade_a.submit(user1, make_trade_details())
        trade_b = Trade(clock=fake_clock)
        trade_b.submit(user1, make_trade_details())
        store.save(trade_a)
        store.save(trade_b)

        assert {t.id for t in store.list()} == {trade_a.id, trade_b.id}
