"""HTTP interfaces for deterministic Aave portfolio stress analysis."""

from typing import Annotated

from fastapi import FastAPI, Query

from .fixtures import demo_scenario
from .scenario import Scenario
from .stress import stress_replay

app = FastAPI(title="Aave Oracle Risk Monitor", version="0.2.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/demo")
def demo(oracle_delay_blocks: Annotated[int, Query(ge=0, le=100_000)] = 2) -> dict:
    return stress_replay(demo_scenario(oracle_delay_blocks))


@app.post("/v1/replay")
def replay(scenario: Scenario) -> dict:
    return stress_replay(scenario)
