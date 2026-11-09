"""Portfolio-level liquidation exposure and stress scenario aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from .engine import Position
from .opportunity import LiquidationPolicy, liquidation_opportunity


@dataclass(frozen=True)
class PortfolioRisk:
    collateral_usd: float
    debt_usd: float
    weighted_health_factor: float
    liquidatable_positions: int
    repay_usd: float
    bad_debt_usd: float
    liquidation_profit_usd: float
    positions: tuple[dict, ...]

    def as_dict(self) -> dict:
        return {"collateral_usd": self.collateral_usd, "debt_usd": self.debt_usd,
                "weighted_health_factor": self.weighted_health_factor,
                "liquidatable_positions": self.liquidatable_positions, "repay_usd": self.repay_usd,
                "bad_debt_usd": self.bad_debt_usd, "liquidation_profit_usd": self.liquidation_profit_usd,
                "positions": list(self.positions)}


def aggregate_risk(
    positions: Sequence[Position],
    prices: Mapping[str, float] | float | None = None,
    policy: LiquidationPolicy = LiquidationPolicy(),
) -> PortfolioRisk:
    """Aggregate health factors and liquidation economics across a portfolio."""
    if not positions:
        raise ValueError("positions cannot be empty")
    rows: list[dict] = []
    collateral_usd = debt_usd = repay_usd = bad_debt_usd = profit_usd = 0.0
    for position in positions:
        if prices is None:
            price = position.collateral_price
        elif isinstance(prices, Mapping):
            if position.id not in prices:
                raise ValueError(f"missing price for position {position.id}")
            price = float(prices[position.id])
        else:
            price = float(prices)
        if price <= 0:
            raise ValueError("scenario prices must be positive")
        row = liquidation_opportunity(position, price, policy)
        row["bad_debt_usd"] = max(0.0, position.debt - row["repay"] if row["liquidatable"] else 0.0)
        rows.append(row)
        collateral_usd += position.collateral * price
        debt_usd += position.debt
        repay_usd += row["repay"]
        bad_debt_usd += row["bad_debt_usd"]
        profit_usd += row["profit_usd"]
    weighted_hf = sum(row["health_factor"] * position.debt for row, position in zip(rows, positions)) / debt_usd
    return PortfolioRisk(collateral_usd, debt_usd, weighted_hf, sum(row["liquidatable"] for row in rows),
                         repay_usd, bad_debt_usd, profit_usd, tuple(rows))


def stress_scenarios(
    positions: Sequence[Position],
    price_factors: Sequence[float],
    policy: LiquidationPolicy = LiquidationPolicy(),
) -> list[dict]:
    """Run a common collateral-price shock and return comparable risk rows."""
    if not price_factors:
        raise ValueError("price_factors cannot be empty")
    scenarios = []
    for factor in price_factors:
        if factor <= 0:
            raise ValueError("price factors must be positive")
        risk = aggregate_risk(positions, {p.id: p.collateral_price * factor for p in positions}, policy)
        row = risk.as_dict()
        row["price_factor"] = factor
        scenarios.append(row)
    return scenarios
