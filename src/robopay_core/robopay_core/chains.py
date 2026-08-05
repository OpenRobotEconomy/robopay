"""Per-network configuration: RPC env var and token contract addresses.
"""

CHAINS = {
    "base-sepolia": {
        "chain_id": 84532,
        "rpc_env": "BASE_SEPOLIA_RPC_URL",
        "public_rpc": "https://sepolia.base.org",
        "escrow": "0x11860A5EAF6DF1E95e34B07628C4924Ef127d9C9",
        "tokens": {
            "USDC": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        },
    },
    "base": {
        "chain_id": 8453,
        "rpc_env": "BASE_MAINNET_RPC_URL",
        "public_rpc": "https://mainnet.base.org",
        "tokens": {
            "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        },
    },
}


def token_address(chain: str, symbol: str) -> str:
    try:
        return CHAINS[chain]["tokens"][symbol]
    except KeyError:
        raise ValueError(f"Unknown token {symbol} on chain {chain}") from None