"""Compare risk outcomes across oracle delays with fixed scenario inputs."""

from typing import Annotated

from pydantic import Field, model_validator

from .scenario import Config, Contract, Scenario
from .stress import stress_replay

Lag = Annotated[int, Field(ge=0, le=100_000)]


class LagStudy(Contract):
    scenario: Scenario
    lags: list[Lag] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def check_study(self) -> "LagStudy":
        if len(self.lags) != len(set(self.lags)):
            raise ValueError("oracle delays must be unique")
        legs = {(row.account, row.asset) for row in self.scenario.initial_balances}
        for frame in self.scenario.frames:
            legs.update((row.account, row.asset) for row in frame.balance_updates)
        if len(legs) * len(self.scenario.frames) * len(self.lags) * self.scenario.config.max_rounds > 2_000_000:
            raise ValueError("comparison exceeds the reserve-leg work budget")
        return self


def compare_lags(study: LagStudy) -> dict:
    results = []
    for lag in sorted(study.lags):
        config = Config.model_validate({**study.scenario.config.model_dump(), "oracle_delay_blocks": lag})
        frames = stress_replay(study.scenario.model_copy(update={"config": config}))
        first = next((frame["block"] for frame in frames["frames"] if frame["liquidations"]), None)
        results.append({"oracle_delay_blocks": lag, "first_liquidation_block": first, **frames["summary"]})
    return {"comparisons": results}
