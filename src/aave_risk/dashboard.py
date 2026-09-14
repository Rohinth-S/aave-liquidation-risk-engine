"""Inspect collateral shocks, oracle lag, and liquidation exposure."""

import json
import os
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from aave_risk.fixtures import demo_scenario
from aave_risk.comparison import LagStudy, compare_lags
from aave_risk.scenario import Scenario
from aave_risk.stress import stress_replay

st.set_page_config(page_title="Aave Oracle Risk", layout="wide")
st.title("Aave Oracle Risk")
source = st.sidebar.file_uploader("Scenario JSON", type=["json"])
if source is None:
    delay = st.sidebar.slider("Oracle delay (blocks)", 0, 8, 2)
try:
    scenario = Scenario.model_validate_json(source.getvalue()) if source else demo_scenario(delay)
    api = os.getenv("AAVE_RISK_API")
    if api:
        request = Request(
            f"{api.rstrip('/')}/v1/replay", data=scenario.model_dump_json().encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(request, timeout=15) as response:
            report = json.load(response)
    else:
        report = stress_replay(scenario)
except (OSError, ValueError) as exc:
    st.error(f"Replay failed. {exc}")
    st.stop()

frames = report["frames"]
last = frames[-1]
block, exposed, gas, loss = st.columns(4)
block.metric("Final block", last["block"])
exposed.metric("Eligible before liquidation", last["eligible_before_rounds"])
gas.metric("Total modeled gas (USD)", f"{sum(f['gas_usd'] for f in frames):,.0f}")
loss.metric("Final collateral shortfall (USD)", f"{last['shortfall_usd']:,.0f}")
price_tab, risk_tab, alert_tab, comparison_tab = st.tabs(["Oracle and market", "Positions and rounds", "Alerts", "Lag comparison"])
with price_tab:
    asset = st.selectbox("Reserve", sorted(last["market_prices_usd"]))
    prices = pd.DataFrame([
        {"block": f["block"], "Market": f["market_prices_usd"][asset], "Oracle": f["oracle_prices_usd"][asset]}
        for f in frames
    ]).set_index("block")
    st.line_chart(prices, x_label="Block", y_label="USD")
    st.bar_chart(pd.DataFrame(frames).set_index("block")["eligible_before_rounds"], y_label="Eligible accounts")
with risk_tab:
    selected = st.selectbox("Block", [f["block"] for f in frames], index=len(frames)-1)
    frame = next(f for f in frames if f["block"] == selected)
    st.caption(f"Oracle block {frame['oracle_block']} · Age {frame['oracle_age_blocks']} blocks")
    if frame["stale_oracle"]:
        st.warning("The selected block uses a stale oracle mark.")
    st.dataframe(frame["positions"], hide_index=True)
    st.bar_chart(pd.DataFrame(frame["reserve_exposure"]).T, y_label="USD")
    st.dataframe(pd.DataFrame(frame["rounds"]).drop(columns=["sold_units", "price_impact_usd"], errors="ignore"))
with alert_tab:
    st.dataframe(report["alerts"], hide_index=True)
    st.subheader("Status changes")
    st.dataframe(report["alert_transitions"], hide_index=True)
with comparison_tab:
    candidates = st.multiselect("Oracle delays to compare", list(range(9)), default=[0, 2, 4])
    if candidates and st.button("Run comparison"):
        try:
            study = LagStudy(scenario=scenario, lags=candidates)
            if api:
                request = Request(f"{api.rstrip('/')}/v1/compare", data=study.model_dump_json().encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=20) as response:
                    comparison = json.load(response)
            else:
                comparison = compare_lags(study)
            st.dataframe(comparison["comparisons"], hide_index=True)
        except (OSError, ValueError) as exc:
            st.error(f"Comparison failed. {exc}")
st.download_button("Download report", json.dumps(report, indent=2), "risk-report.json", "application/json")
