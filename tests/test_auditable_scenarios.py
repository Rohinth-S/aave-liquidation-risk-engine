from aave_risk.fixtures import demo_scenario
from aave_risk.scenario import Scenario
from aave_risk.stress import stress_replay


def test_sparse_mark_history_reports_bootstrap_and_stale_pause():
    fixture = demo_scenario(2).model_dump()
    fixture["frames"] = [fixture["frames"][0], fixture["frames"][3], fixture["frames"][-1]]
    fixture["config"].update(max_oracle_age_blocks=2, pause_on_stale_oracle=True)
    result = stress_replay(Scenario.model_validate(fixture))
    first, gap, later = result["frames"]
    assert first["oracle_bootstrap"] and first["oracle_block"] == 100
    assert not gap["oracle_bootstrap"] and gap["oracle_block"] == 100
    assert gap["stale_oracle"] and gap["liquidations_paused"]
    assert later["liquidations_paused"] and later["liquidations"] == 0

def test_reserve_exposure_and_recovery_agree_with_closed_leg_updates():
    fixture = demo_scenario(0).model_dump()
    fixture["config"]["simulate_liquidations"] = False
    fixture["frames"][5]["balance_updates"] = [
        {"account": "B", "asset": "WETH"}, {"account": "B", "asset": "USDC"},
    ]
    result = stress_replay(Scenario.model_validate(fixture))
    assert not any(row["account"] == "B" for row in result["frames"][5]["positions"])
    assert any(row["block"] == 105 and row["account"] == "B" and row["to"] == "ok"
               for row in result["alert_transitions"])
    for frame in result["frames"]:
        assert frame["debt_usd"] == sum(value["debt_usd"] for value in frame["reserve_exposure"].values())
