from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Position:
    id: str
    collateral: float
    collateral_price: float
    debt: float
    liquidation_threshold: float = 0.8
    bonus: float = 0.05

    def __post_init__(self) -> None:
        if not self.id or self.collateral <= 0 or self.collateral_price <= 0 or self.debt <= 0:
            raise ValueError("position id, collateral, price, and debt must be positive")
        if not 0 < self.liquidation_threshold <= 1 or self.bonus < 0:
            raise ValueError("liquidation threshold must be in (0,1] and bonus cannot be negative")

    def health_factor(self, price: float | None = None) -> float:
        effective_price = self.collateral_price if price is None else price
        if effective_price < 0:
            raise ValueError("price cannot be negative")
        return self.collateral * effective_price * self.liquidation_threshold / self.debt

def shock(position: Position, price_factor: float, gas_usd: float = 12, oracle_delay_blocks: int = 0, gas_multiplier: float = 1.0) -> dict:
    if price_factor <= 0 or gas_usd < 0 or oracle_delay_blocks < 0 or gas_multiplier <= 0:
        raise ValueError("shock factor, gas, delay, and multiplier must be valid")
    price = position.collateral_price * price_factor
    hf = position.health_factor(price)
    liquidatable = hf < 1
    repay = min(position.debt * 0.5, position.collateral * price * position.liquidation_threshold) if liquidatable else 0
    seized = repay * (1 + position.bonus) / price if liquidatable else 0
    effective_gas = gas_usd * gas_multiplier
    return {"id": position.id, "price": price, "health_factor": hf, "liquidatable": liquidatable, "repay": repay, "seized_collateral": seized, "gas_usd": effective_gas, "oracle_delay_blocks": oracle_delay_blocks, "bad_debt": max(0, position.debt - repay) if liquidatable else 0}

def replay(positions, factors=(-0.95, -0.8, -0.6, -0.4, -0.2, 0.0)):
    return [shock(position, 1 + factor, oracle_delay_blocks=2 if factor < -0.5 else 0, gas_multiplier=1.5 if factor < -0.5 else 1.0) for position in positions for factor in factors]

def alert(row: dict) -> str:
    return "critical" if row["health_factor"] < 0.95 else "watch" if row["health_factor"] < 1.1 else "ok"
