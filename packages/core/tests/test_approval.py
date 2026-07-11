from trade_approval_core.approval import evaluate_trade


def test_within_limit_is_approved() -> None:
    result = evaluate_trade(amount=100, limit=200)
    assert result.approved
    assert result.reason == "within limit"


def test_over_limit_is_rejected() -> None:
    result = evaluate_trade(amount=300, limit=200)
    assert not result.approved
    assert result.reason == "exceeds limit"
