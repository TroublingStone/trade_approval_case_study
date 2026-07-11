from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .enums import Currency
from .errors import (
    InvalidDateOrderError,
    NonPositiveNotionalAmountError,
    NonPositiveStrikeRateError,
    NotionalCurrencyMismatchError,
)


@dataclass(frozen=True, kw_only=True)
class TradeDetails:
    trading_entity: str
    counterparty: str
    notional_currency: Currency
    notional_amount: Decimal
    underlying: tuple[Currency, Currency]
    trade_date: date
    value_date: date
    delivery_date: date
    strike_rate: Decimal

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not (self.trade_date <= self.value_date <= self.delivery_date):
            raise InvalidDateOrderError(self.trade_date, self.value_date, self.delivery_date)
        if self.notional_amount <= 0:
            raise NonPositiveNotionalAmountError(self.notional_amount)
        if self.notional_currency not in self.underlying:
            raise NotionalCurrencyMismatchError(self.notional_currency, self.underlying)
        if self.strike_rate <= 0:
            raise NonPositiveStrikeRateError(self.strike_rate)
