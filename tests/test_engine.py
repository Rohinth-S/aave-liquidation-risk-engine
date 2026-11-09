from aave_risk.engine import Position,shock,alert
def test_healthy_position():
 r=shock(Position("x",10,2000,10000),1); assert not r["liquidatable"] and alert(r)=="ok"
def test_stress_triggers_liquidation():
 r=shock(Position("x",10,2000,10000),.4); assert r["liquidatable"] and r["bad_debt"]>=0
