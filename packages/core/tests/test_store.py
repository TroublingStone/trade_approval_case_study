import pytest
from trade_approval_core.errors import TradeNotFoundError
from trade_approval_core.store import TradeStore
from trade_approval_core.trade import Trade
from trade_approval_core.types import TradeId


def test_get_unknown_trade_id_raises_not_found():
    store = TradeStore()
    missing_id = TradeId("does-not-exist")

    with pytest.raises(TradeNotFoundError) as exc_info:
        store.get(missing_id)
    assert exc_info.value.trade_id == missing_id


def test_list_on_empty_store_is_empty():
    store = TradeStore()
    assert store.list() == []


def test_save_then_get_returns_same_trade(fake_clock):
    store = TradeStore()
    trade = Trade(clock=fake_clock)

    store.save(trade)

    assert store.get(trade.id) is trade


def test_list_reflects_saved_trades(fake_clock):
    store = TradeStore()
    trade_a = Trade(clock=fake_clock)
    trade_b = Trade(clock=fake_clock)

    store.save(trade_a)
    store.save(trade_b)

    assert {t.id for t in store.list()} == {trade_a.id, trade_b.id}


def test_mutations_after_save_are_visible_without_resaving(fake_clock, user1, make_trade_details):
    # Trade mutates its internal event log in place, so the object returned by
    # get() already reflects actions taken after save() -- no need to save()
    # again after every action.
    store = TradeStore()
    trade = Trade(clock=fake_clock)
    store.save(trade)

    trade.submit(user1, make_trade_details())

    assert store.get(trade.id).state == trade.state
