from trade_approval_core.enums import Action, State

ALLOWED_TRANSITIONS: dict[tuple[State, Action], State] = {
    (State.DRAFT,             Action.SUBMIT):          State.PENDING_APPROVAL,
    (State.PENDING_APPROVAL,  Action.APPROVE):         State.APPROVED,
    (State.PENDING_APPROVAL,  Action.UPDATE):          State.NEEDS_REAPPROVAL,
    (State.PENDING_APPROVAL,  Action.CANCEL):          State.CANCELLED,
    (State.NEEDS_REAPPROVAL,  Action.APPROVE):         State.APPROVED,
    (State.NEEDS_REAPPROVAL,  Action.CANCEL):          State.CANCELLED,
    (State.APPROVED,          Action.SEND_TO_EXECUTE): State.SENT_TO_COUNTERPARTY,
    (State.APPROVED,          Action.CANCEL):          State.CANCELLED,
    (State.SENT_TO_COUNTERPARTY, Action.BOOK):         State.EXECUTED,
    (State.SENT_TO_COUNTERPARTY, Action.CANCEL):       State.CANCELLED,
}

class Trade:
    def __init__(self) -> None:
        pass
