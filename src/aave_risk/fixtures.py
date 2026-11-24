"""A multi-asset collateral shock and delayed oracle fixture."""

from .scenario import Scenario


def demo_scenario(oracle_delay_blocks: int = 2) -> Scenario:
    return Scenario.model_validate({
        "reserves": [
            {"asset": "WETH", "threshold": 0.8, "liquidation_bonus": 0.06, "market_depth_usd": 80_000},
            {"asset": "WBTC", "threshold": 0.75, "market_depth_usd": 500_000},
            {"asset": "USDC", "threshold": 0.85, "market_depth_usd": 10_000_000},
        ],
        "initial_balances": [
            {"account": "A", "asset": "WETH", "collateral": 10},
            {"account": "A", "asset": "WBTC", "collateral": 0.1},
            {"account": "A", "asset": "USDC", "debt": 16_000},
            {"account": "B", "asset": "WETH", "collateral": 5},
            {"account": "B", "asset": "USDC", "debt": 7_100},
            {"account": "C", "asset": "WBTC", "collateral": 0.5},
            {"account": "C", "asset": "USDC", "debt": 4_000},
        ],
        "frames": [
            {"block": 100 + i, "prices_usd": {"WETH": eth, "WBTC": btc, "USDC": 1}, "gas_usd": gas}
            for i, (eth, btc, gas) in enumerate((
                (2_200, 60_000, 12), (2_000, 58_000, 18), (1_600, 52_000, 32),
                (1_200, 46_000, 50), (1_180, 45_000, 55), (1_250, 46_000, 35),
                (1_350, 46_500, 25), (1_500, 47_000, 18),
            ))
        ],
        "config": {"oracle_delay_blocks": oracle_delay_blocks},
    })
