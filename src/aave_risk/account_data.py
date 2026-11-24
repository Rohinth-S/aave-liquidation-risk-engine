"""Read only Aave V3 account totals at one explicit historical block."""

import re

from web3 import Web3

from .rpc import JsonRpcClient

SELECTOR = Web3.keccak(text="getUserAccountData(address)")[:4].hex()


def read_account_data(
    rpc: JsonRpcClient, *, chain_id: int, block_number: int, pool: str, accounts: list[str],
    base_decimals: int = 8,
) -> dict:
    if block_number < 0 or not 0 <= base_decimals <= 36 or not accounts:
        raise ValueError("requires a nonnegative block number, base decimals in [0, 36], and account list")
    target = Web3.to_checksum_address(pool)
    addresses = list(dict.fromkeys(Web3.to_checksum_address(account) for account in accounts))
    if int(rpc.call("eth_chainId", []), 16) != chain_id:
        raise ValueError("RPC chain ID does not match the requested deployment")
    block = rpc.call("eth_getBlockByNumber", [hex(block_number), False])
    if (
        not isinstance(block, dict) or int(block.get("number", "0x0"), 16) != block_number
        or not re.fullmatch(r"0x[0-9a-fA-F]{64}", str(block.get("hash")))
    ):
        raise ValueError("provider did not return the requested block")
    block_ref = {"blockHash": block["hash"], "requireCanonical": True}
    scale = 10 ** base_decimals
    accounts_data = []
    for address in addresses:
        call = {"to": target, "data": "0x" + SELECTOR + address[2:].lower().rjust(64, "0")}
        raw = rpc.call("eth_call", [call, block_ref])
        if not isinstance(raw, str) or not re.fullmatch(r"0x[0-9a-fA-F]{384}", raw):
            raise ValueError("pool call did not return six ABI words")
        collateral, debt, available, threshold, ltv, hf = Web3().codec.decode(
            ["uint256"] * 6, bytes.fromhex(raw[2:]),
        )
        accounts_data.append({
            "account": address, "collateral_base": collateral / scale, "debt_base": debt / scale,
            "available_borrows_base": available / scale, "liquidation_threshold_bps": threshold,
            "ltv_bps": ltv, "health_factor": hf / 10**18 if debt else None,
        })
    return {
        "chain_id": chain_id, "block": block_number, "block_hash": block["hash"],
        "pool": target, "base_decimals": base_decimals, "accounts": accounts_data,
    }
