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
