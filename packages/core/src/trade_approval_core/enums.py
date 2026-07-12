from enum import StrEnum


class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"


class State(StrEnum):
    DRAFT = "Draft"
    PENDING_APPROVAL = "PendingApproval"
    NEEDS_REAPPROVAL = "NeedsReapproval"
    APPROVED = "Approved"
    SENT_TO_COUNTERPARTY = "SentToCounterparty"
    EXECUTED = "Executed"
    CANCELLED = "Cancelled"

class Action(StrEnum):
    SUBMIT = "Submit"
    APPROVE = "Approve"
    UPDATE = "Update"
    CANCEL = "Cancel"
    SEND_TO_EXECUTE = "SendToExecute"
    BOOK = "Book"


class Direction(StrEnum):
    BUY = "Buy"
    SELL = "Sell"


class Style(StrEnum):
    FORWARD = "Forward"
