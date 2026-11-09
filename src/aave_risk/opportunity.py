"""Liquidation sizing and profitability calculations."""
from __future__ import annotations

from dataclasses import dataclass
from .engine import Position


@dataclass(frozen=True)
class LiquidationPolicy:
    close_factor: float = 0.5
    min_profit_usd: float = 5.0
    gas_usd: float = 12.0

    def __post_init__(self) -> None:
        if not 0 < self.close_factor <= 1:
            raise ValueError("close_factor must be in (0, 1]")
        if self.min_profit_usd < 0 or self.gas_usd < 0:
            raise ValueError("profit and gas thresholds cannot be negative")


def liquidation_opportunity(
    position: Position,
    price: float,
    policy: LiquidationPolicy = LiquidationPolicy(),
) -> dict:
    """Return a deterministic, close-factor bounded liquidation decision."""

    if price <= 0:
        raise ValueError("price must be positive")
    health_factor = position.health_factor(price)
    max_repay = min(position.debt * policy.close_factor, position.collateral * price * position.liquidation_threshold)
    seized = max_repay * (1 + position.bonus) / price if health_factor < 1 else 0.0
    bonus_value = max(0.0, seized * price - max_repay)
    profit = bonus_value - policy.gas_usd
    return {
        "id": position.id,
        "price": price,
        "health_factor": health_factor,
        "liquidatable": health_factor < 1,
        "repay": max_repay if health_factor < 1 else 0.0,
        "seized_collateral": seized,
        "bonus_value_usd": bonus_value,
        "gas_usd": policy.gas_usd,
        "profit_usd": profit if health_factor < 1 else 0.0,
        "profitable": health_factor < 1 and profit >= policy.min_profit_usd,
    }
