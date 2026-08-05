import pytest
from aave_risk.engine import Position, shock, alert
def test_healthy_position():
    r=shock(Position("x",10,2000,10000),1); assert not r["liquidatable"] and alert(r)=="ok"
def test_stress_triggers_liquidation():
    r=shock(Position("x",10,2000,10000),.4,oracle_delay_blocks=3,gas_multiplier=2); assert r["liquidatable"] and r["bad_debt"]>=0 and r["oracle_delay_blocks"]==3 and r["gas_usd"]==24
def test_position_validation():
    with pytest.raises(ValueError): Position("x",0,100,1)
