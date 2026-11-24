"""Chronological multi-reserve stress inputs."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Key = Annotated[str, Field(min_length=1, max_length=100)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Reserve(Contract):
    asset: Key
    threshold: Annotated[float, Field(gt=0, le=1)]
    liquidation_bonus: Annotated[float, Field(ge=0, le=1)] = 0.05
    market_depth_usd: Positive


class Balance(Contract):
    account: Key
    asset: Key
    collateral: Nonnegative = 0
    debt: Nonnegative = 0


class MarketFrame(Contract):
    block: Annotated[int, Field(ge=0)]
    prices_usd: dict[Key, Positive]
    gas_usd: Nonnegative = 12
    balance_updates: list[Balance] = Field(default_factory=list, max_length=20_000)


class Config(Contract):
    oracle_delay_blocks: Annotated[int, Field(ge=0, le=100_000)] = 0
    close_factor: Annotated[float, Field(gt=0, le=1)] = 0.5
    max_rounds: Annotated[int, Field(ge=1, le=20)] = 3
    max_round_price_impact: Annotated[float, Field(ge=0, lt=1)] = 0.2
    simulate_liquidations: bool = True
    watch_threshold: Annotated[float, Field(ge=1, le=5)] = 1.1


class Scenario(Contract):
    reserves: list[Reserve] = Field(min_length=1, max_length=256)
    initial_balances: list[Balance] = Field(min_length=1, max_length=20_000)
    frames: list[MarketFrame] = Field(min_length=1, max_length=4_096)
    config: Config = Field(default_factory=Config)

    @model_validator(mode="after")
    def validate_replay(self) -> "Scenario":
        assets = {reserve.asset for reserve in self.reserves}
        if len(assets) != len(self.reserves):
            raise ValueError("reserve assets must be unique")
        blocks = [frame.block for frame in self.frames]
        if blocks != sorted(set(blocks)):
            raise ValueError("market frames must have strictly increasing block numbers")
        accounts = set()
        for balances in [self.initial_balances, *(frame.balance_updates for frame in self.frames)]:
            keys = {(balance.account, balance.asset) for balance in balances}
            if len(keys) != len(balances):
                raise ValueError("each account and asset may appear once per balance snapshot")
            if any(asset not in assets for _, asset in keys):
                raise ValueError("balance asset is missing from reserves")
            accounts.update(account for account, _ in keys)
        if any(set(frame.prices_usd) != assets for frame in self.frames):
            raise ValueError("each market frame must price every reserve")
        if len(accounts) * len(self.frames) * self.config.max_rounds > 500_000:
            raise ValueError("replay exceeds the account-frame-round budget")
        return self
