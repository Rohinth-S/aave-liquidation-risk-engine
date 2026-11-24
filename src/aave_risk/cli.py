"""Run a portfolio stress replay or read an explicit historical account snapshot."""

import argparse
import json
from pathlib import Path

from .fixtures import demo_scenario
from .scenario import Scenario
from .stress import stress_replay


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay oracle risk or read pinned Aave account data")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--input", type=Path, help="path to a normalized scenario JSON")
    sources.add_argument("--account", action="append", help="read account totals for this address (repeatable)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-scenario", type=Path, help="export the replay inputs")
    parser.add_argument("--oracle-delay-blocks", type=int, help="override replay delay")
    parser.add_argument("--pool", help="Aave v3 Pool proxy address for account reads")
    parser.add_argument("--block", type=int, help="pinned historical block")
    parser.add_argument("--chain-id", type=int, help="expected chain ID for account reads")
    parser.add_argument("--network", default="ethereum")
    parser.add_argument("--base-decimals", type=int, default=8)
    args = parser.parse_args()

    try:
        if args.account:
            from .account_data import read_account_data
            from .rpc import JsonRpcClient

            if args.pool is None or args.block is None or args.chain_id is None:
                parser.error("--account requires --pool, --block and --chain-id")
            if args.write_scenario or args.oracle_delay_blocks is not None:
                parser.error("replay options require a scenario or the demo")
            result = read_account_data(
                JsonRpcClient(network=args.network), chain_id=args.chain_id, block_number=args.block,
                pool=args.pool, accounts=args.account, base_decimals=args.base_decimals,
            )
        else:
            scenario = (
                Scenario.model_validate_json(args.input.read_bytes()) if args.input else demo_scenario()
            )
            if args.oracle_delay_blocks is not None:
                values = scenario.model_dump()
                values["config"]["oracle_delay_blocks"] = args.oracle_delay_blocks
                scenario = Scenario.model_validate(values)
            if args.write_scenario:
                args.write_scenario.parent.mkdir(parents=True, exist_ok=True)
                args.write_scenario.write_text(scenario.model_dump_json(indent=2) + "\n", encoding="utf-8")
            result = stress_replay(scenario)

        payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(payload, end="")


if __name__ == "__main__":
    main()
