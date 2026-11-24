from fastapi.testclient import TestClient
from web3 import Web3

from aave_risk.account_data import read_account_data
from aave_risk.api import app
from aave_risk.fixtures import demo_scenario
from aave_risk.scenario import Scenario
from aave_risk.stress import stress_replay


def test_oracle_lag_changes_liquidation_timing_and_preserves_prefix():
    immediate = stress_replay(demo_scenario(0))
    delayed = stress_replay(demo_scenario(2))
    first = next(f["block"] for f in immediate["frames"] if f["liquidations"])
    later = next(f["block"] for f in delayed["frames"] if f["liquidations"])
    assert later == first + 2
    assert any(a["status"] == "oracle_gap" for a in delayed["alerts"])
    assert all(f["oracle_block"] <= f["block"] for f in delayed["frames"])
    values = demo_scenario(2).model_dump()
    values["frames"] = values["frames"][:4]
    assert stress_replay(Scenario.model_validate(values))["frames"] == delayed["frames"][:4]


def test_stress_replay_applies_absolute_balance_updates_and_gas():
    data = demo_scenario(0).model_dump()
    data["frames"][1]["balance_updates"] = [{"account": "B", "asset": "USDC", "debt": 0}]
    report = stress_replay(Scenario.model_validate(data))
    for frame in report["frames"][1:]:
        position = next(p for p in frame["positions"] if p["account"] == "B")
        assert position["debt_usd"] == 0 and position["market_health_factor"] is None
    assert any(round_["price_impact_usd"]["WETH"] > 0 for f in report["frames"] for round_ in f["rounds"])
    for index, frame in enumerate(report["frames"]):
        assert frame["gas_usd"] == frame["liquidations"] * data["frames"][index]["gas_usd"]


def test_replay_api_validates_input_and_matches_demo():
    with TestClient(app) as client:
        scenario = demo_scenario()
        response = client.post("/v1/replay", json=scenario.model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json() == client.get("/v1/demo").json()
        invalid = scenario.model_dump()
        invalid["frames"][0]["prices_usd"].pop("WETH")
        assert client.post("/v1/replay", json=invalid).status_code == 422


def test_account_snapshot_pins_hash_and_decodes_units():
    block_hash = "0x" + "ab" * 32

    class Provider:
        def call(self, method, params):
            if method == "eth_chainId":
                return "0x1"
            if method == "eth_getBlockByNumber":
                assert params == ["0x64", False]
                return {"hash": block_hash, "number": "0x64"}
            assert method == "eth_call" and params[1]["blockHash"] == block_hash
            assert params[1]["requireCanonical"] is True
            assert params[0]["data"].startswith("0xbf92857c")
            values = [2_000 * 10**8, 1_000 * 10**8, 500 * 10**8, 8_000, 7_500, 16 * 10**17]
            return "0x" + Web3().codec.encode(["uint256"] * 6, values).hex()

    report = read_account_data(
        Provider(), chain_id=1, block_number=100, pool="0x" + "01" * 20, accounts=["0x" + "02" * 20],
    )
    assert report["accounts"][0]["collateral_base"] == 2_000
    assert report["accounts"][0]["health_factor"] == 1.6
