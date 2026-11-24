"""Value positions and apply bounded liquidation feedback in replay order."""

from bisect import bisect_right
from collections import defaultdict

from .scenario import Balance, Config, Reserve, Scenario

Book = dict[str, dict[str, Balance]]


def _apply(book: Book, balances: list[Balance]) -> None:
    for balance in balances:
        book.setdefault(balance.account, {})[balance.asset] = balance


def _values(
    positions: dict[str, Balance], prices: dict[str, float], reserves: dict[str, Reserve],
) -> tuple[float, float, float | None]:
    collateral = sum(leg.collateral * prices[asset] for asset, leg in positions.items())
    debt = sum(leg.debt * prices[asset] for asset, leg in positions.items())
    weighted = sum(
        leg.collateral * prices[asset] * reserves[asset].threshold for asset, leg in positions.items()
    )
    return collateral, debt, weighted / debt if debt else None


def _eligible(hf: float | None) -> bool:
    return hf is not None and hf < 1


def _liquidate(
    book: Book, oracle: dict[str, float], reserves: dict[str, Reserve], config: Config,
) -> tuple[int, float, dict[str, float]]:
    """Model one round at a common oracle price vector."""
    liquidations = 0
    repaid = 0.0
    units_sold: dict[str, float] = defaultdict(float)
    for positions in book.values():
        _, debt, hf = _values(positions, oracle, reserves)
        if not _eligible(hf):
            continue
        assets = {
            asset: leg.collateral * oracle[asset] / (1 + reserves[asset].liquidation_bonus)
            for asset, leg in positions.items()
        }
        capacity = sum(assets.values())
        repayment = min(debt * config.close_factor, capacity)
        if repayment <= 1e-9:
            continue
        collateral_fraction = repayment / capacity
        debt_fraction = repayment / debt
        for asset, leg in positions.items():
            sold = leg.collateral * collateral_fraction
            units_sold[asset] += sold
            positions[asset] = leg.model_copy(update={
                "collateral": leg.collateral - sold, "debt": leg.debt * (1 - debt_fraction),
            })
        liquidations += 1
        repaid += repayment
    return liquidations, repaid, units_sold


def stress_replay(scenario: Scenario) -> dict:
    config = scenario.config
    reserves = {reserve.asset: reserve for reserve in scenario.reserves}
    book: Book = {}
    _apply(book, scenario.initial_balances)
    history_blocks: list[int] = []
    history_values: list[dict[str, float]] = []
    frames = []

    for frame in scenario.frames:
        _apply(book, frame.balance_updates)
        market = dict(frame.prices_usd)
        delayed = config.oracle_delay_blocks > 0
        if delayed and history_blocks:
            index = max(0, bisect_right(history_blocks, frame.block - config.oracle_delay_blocks) - 1)
            oracle = history_values[index].copy()
            oracle_block = history_blocks[index]
        else:
            oracle = market.copy()
            oracle_block = frame.block
        initial_count = sum(_eligible(_values(legs, oracle, reserves)[2]) for legs in book.values())
        operations = 0
        repayments = 0.0
        rounds = []

        if config.simulate_liquidations:
            for round_number in range(1, config.max_rounds + 1):
                count, repaid, sold = _liquidate(book, oracle, reserves, config)
                if not count:
                    break
                before_impact = market.copy()
                for asset, quantity in sold.items():
                    fraction = min(
                        config.max_round_price_impact,
                        quantity * market[asset] / reserves[asset].market_depth_usd,
                    )
                    market[asset] *= 1 - fraction
                rounds.append({
                    "round": round_number, "liquidations": count, "repaid_usd": repaid,
                    "sold_units": dict(sold), "gas_usd": count * frame.gas_usd,
                    "price_impact_usd": {asset: before_impact[asset] - market[asset] for asset in reserves},
                })
                operations += count
                repayments += repaid
                if not delayed or not history_blocks:
                    oracle = market.copy()

        positions = []
        for account, legs in sorted(book.items()):
            collateral, debt, market_hf = _values(legs, market, reserves)
            _, _, oracle_hf = _values(legs, oracle, reserves)
            if _eligible(oracle_hf):
                status = "liquidatable"
            elif _eligible(market_hf):
                status = "oracle_gap"
            elif oracle_hf is not None and oracle_hf < config.watch_threshold:
                status = "watch"
            else:
                status = "ok"
            positions.append({
                "account": account, "market_health_factor": market_hf, "oracle_health_factor": oracle_hf,
                "collateral_usd": collateral, "debt_usd": debt, "shortfall_usd": max(0.0, debt - collateral),
                "status": status,
            })
        history_blocks.append(frame.block)
        history_values.append(market.copy())
        frames.append({
            "block": frame.block, "oracle_block": oracle_block, "oracle_age_blocks": frame.block - oracle_block,
            "market_prices_usd": market, "oracle_prices_usd": oracle,
            "eligible_before_rounds": initial_count,
            "eligible_after_rounds": sum(row["status"] == "liquidatable" for row in positions),
            "liquidations": operations, "repaid_usd": repayments, "gas_usd": operations * frame.gas_usd,
            "shortfall_usd": sum(row["shortfall_usd"] for row in positions),
            "debt_usd": sum(row["debt_usd"] for row in positions),
            "rounds": rounds, "positions": positions,
        })
    return {
        "config": config.model_dump(), "frames": frames,
        "alerts": [
            {"block": frame["block"], "account": row["account"], "status": row["status"]}
            for frame in frames for row in frame["positions"] if row["status"] != "ok"
        ],
    }
