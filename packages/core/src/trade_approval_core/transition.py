from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from trade_approval_core.errors import UnauthorizedActionError
from trade_approval_core.types import UserId

if TYPE_CHECKING:
    from trade_approval_core.trade import Trade


@dataclass(frozen=True)
class Transition(ABC):
    """Decides *who* may take an action from a given state.

    Carries no target state -- ACTION_TO_STATE_MAP (trade.py) is the single
    source of truth for what state an action produces, derived from the event
    type it appends. A Transition's only job is authorize().

    Rules check the UserId against the trade's event history only; the UserId
    itself is trusted, authenticated input (see Trade's docstring).
    """

    @abstractmethod
    def authorize(self, trade: "Trade", user: UserId) -> None:
        """Raise UnauthorizedActionError if `user` may not take this transition."""


@dataclass(frozen=True)
class RequesterOrApprover(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user not in (trade.requester, trade.approver):
            raise UnauthorizedActionError(user, "must be the requester or approver")


@dataclass(frozen=True)
class RequesterOnly(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user != trade.requester:
            raise UnauthorizedActionError(user, "must be the original requester")


@dataclass(frozen=True)
class NotRequester(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user == trade.requester:
            raise UnauthorizedActionError(user, "the requester cannot approve their own submission (four-eyes)")


@dataclass(frozen=True)
class ApproverOnly(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user != trade.approver:
            raise UnauthorizedActionError(user, "must be the approver")


@dataclass(frozen=True)
class Unrestricted(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        return None
