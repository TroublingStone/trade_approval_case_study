import pytest
from trade_approval_core.errors import TradeNotFoundError
from trade_approval_core.store import InMemoryTradeStore
from trade_approval_core.trade import Trade
from trade_approval_core.types import TradeId


def test_get_unknown_trade_id_raises_not_found():
    store = InMemoryTradeStore()
    missing_id = TradeId("does-not-exist")

    with pytest.raises(TradeNotFoundError) as exc_info:
        store.get(missing_id)
    assert exc_info.value.trade_id == missing_id


def test_list_on_empty_store_is_empty():
    store = InMemoryTradeStore()
    assert store.list() == []


def test_save_then_get_returns_same_trade(fake_clock):
    store = InMemoryTradeStore()
    trade = Trade(clock=fake_clock)

    store.save(trade)

    assert store.get(trade.id) is trade


def test_list_reflects_saved_trades(fake_clock):
    store = InMemoryTradeStore()
    trade_a = Trade(clock=fake_clock)
    trade_b = Trade(clock=fake_clock)

    store.save(trade_a)
    store.save(trade_b)

    assert {t.id for t in store.list()} == {trade_a.id, trade_b.id}


def test_mutations_after_save_are_visible_without_resaving(fake_clock, user1, make_trade_details):
    store = InMemoryTradeStore()
    trade = Trade(clock=fake_clock)
    store.save(trade)

    trade.submit(user1, make_trade_details())

    assert store.get(trade.id).state == trade.state


class TestListPagination:
    """list() orders by trade id and honours the cursor contract: `after`
    excludes ids up to and including the cursor, `limit` caps the page.
    """

    @staticmethod
    def _store_with_ids(ids: list[str]) -> InMemoryTradeStore:
        store = InMemoryTradeStore()
        for raw_id in ids:
            trade = Trade()
            trade.id = TradeId(raw_id)
            store.save(trade)
        return store

    def test_list_is_ordered_by_trade_id(self):
        store = self._store_with_ids(["c", "a", "b"])
        assert [t.id for t in store.list()] == ["a", "b", "c"]

    def test_limit_caps_the_page(self):
        store = self._store_with_ids(["a", "b", "c"])
        assert [t.id for t in store.list(limit=2)] == ["a", "b"]

    def test_after_excludes_the_cursor_itself(self):
        store = self._store_with_ids(["a", "b", "c"])
        assert [t.id for t in store.list(after=TradeId("a"))] == ["b", "c"]

    def test_after_and_limit_walk_pages_without_overlap_or_gaps(self):
        store = self._store_with_ids(["a", "b", "c", "d", "e"])
        first = store.list(limit=2)
        second = store.list(limit=2, after=first[-1].id)
        third = store.list(limit=2, after=second[-1].id)
        assert [t.id for t in first + second + third] == ["a", "b", "c", "d", "e"]

    def test_after_beyond_the_last_id_returns_empty(self):
        store = self._store_with_ids(["a", "b"])
        assert store.list(after=TradeId("z")) == []
