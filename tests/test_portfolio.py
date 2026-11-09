import pytest

from aave_risk.engine import Position
from aave_risk.opportunity import LiquidationPolicy
from aave_risk.portfolio import aggregate_risk, stress_scenarios


def test_portfolio_aggregation_tracks_repay_and_bad_debt():
    positions = [Position("safe", 10, 2_000, 10_000), Position("risky", 10, 2_000, 20_000)]
    risk = aggregate_risk(positions, 1_000, LiquidationPolicy(gas_usd=10))
    assert risk.collateral_usd == 20_000
    assert risk.debt_usd == 30_000
    assert risk.liquidatable_positions == 2
    assert risk.repay_usd == pytest.approx(13_000)
    assert risk.bad_debt_usd == pytest.approx(17_000)


def test_stress_scenarios_are_monotonic_for_common_shocks():
    positions = [Position("a", 10, 2_000, 10_000)]
    scenarios = stress_scenarios(positions, [1.0, .8, .4])
    assert [row["price_factor"] for row in scenarios] == [1.0, .8, .4]
    assert scenarios[-1]["liquidatable_positions"] >= scenarios[0]["liquidatable_positions"]
    with pytest.raises(ValueError): stress_scenarios(positions, [0])
