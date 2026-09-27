import pytest
from aave_risk.engine import Position
from aave_risk.opportunity import LiquidationPolicy, liquidation_opportunity


def test_liquidation_respects_close_factor_and_profit_threshold():
    row = liquidation_opportunity(Position("x", 10, 2_000, 10_000), 1_000, LiquidationPolicy(gas_usd=10))
    assert row["liquidatable"]
    assert row["repay"] == pytest.approx(5_000)
    assert row["seized_collateral"] == pytest.approx(5.25)
    assert row["profitable"]


def test_healthy_position_has_no_opportunity():
    row = liquidation_opportunity(Position("x", 10, 2_000, 10_000), 2_000)
    assert row["liquidatable"] is False
    assert row["repay"] == 0

