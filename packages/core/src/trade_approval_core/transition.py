from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from trade_approval_core.enums import State
from trade_approval_core.errors import UnauthorizedActionError
from trade_approval_core.types import UserId

if TYPE_CHECKING:
    from trade_approval_core.trade import Trade


@dataclass(frozen=True)
class Transition(ABC):
    target: State

    @abstractmethod
    def authorize(self, trade: "Trade", user: UserId) -> None:
        """Raise UnauthorizedActionError if `user` may not take this transition."""


@dataclass(frozen=True)
class RequesterOrApprover(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user not in (trade.requester, trade.approver):
            raise UnauthorizedActionError(user, "must be the requester or approver")


@dataclass(frozen=True)
class OriginalRequester(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user != trade.requester:
            raise UnauthorizedActionError(user, "must be the original requester")


@dataclass(frozen=True)
class AnyoneButRequester(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user == trade.requester:
            raise UnauthorizedActionError(user, "approver cannot be the submitter (four-eyes)")


@dataclass(frozen=True)
class ApproverOnly(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        if user != trade.approver:
            raise UnauthorizedActionError(user, "must be the approver")


@dataclass(frozen=True)
class Unrestricted(Transition):
    def authorize(self, trade: "Trade", user: UserId) -> None:
        return None
