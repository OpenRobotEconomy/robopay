"""Thin wrapper around a web3 connection to one chain.
"""

import os

from dotenv import load_dotenv
from web3 import Web3

from .chains import CHAINS

from .erc20_abi import ERC20_ABI
from .chains import token_address

load_dotenv()


class ChainClient:
    def __init__(self, chain: str = "base-sepolia") -> None:
        if chain not in CHAINS:
            raise ValueError(f"Unknown chain: {chain}")
        self.chain = chain
        self.config = CHAINS[chain]

        configured = (os.getenv(self.config["rpc_env"]) or "").strip()
        rpc_url = configured or self.config["public_rpc"]
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.using_public_rpc = not configured

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def block_number(self) -> int:
        return self.w3.eth.block_number

    def chain_id(self) -> int:
        return self.w3.eth.chain_id

    def native_balance(self, address: str) -> str:
        wei = self.w3.eth.get_balance(Web3.to_checksum_address(address))
        return str(self.w3.from_wei(wei, "ether"))

    def token_balance(self, address: str, symbol: str = "USDC") -> str:
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address(self.chain, symbol)),
            abi=ERC20_ABI,
        )
        raw = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
        decimals = contract.functions.decimals().call()
        human = raw / (10 ** decimals)
        return f"{human:.{decimals}f}".rstrip("0").rstrip(".") or "0"