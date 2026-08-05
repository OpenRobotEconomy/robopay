"""Builds and signs the EIP-712 release digest for RobopayEscrow.
"""
from eth_account import Account
from eth_account.messages import encode_typed_data


def build_release_message(chain_id: int, escrow_address: str, escrow: dict,
                          escrow_id: bytes) -> dict:
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Release": [
                {"name": "id", "type": "bytes32"},
                {"name": "payee", "type": "address"},
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "deadline", "type": "uint256"},
                {"name": "terms", "type": "bytes32"},
            ],
        },
        "primaryType": "Release",
        "domain": {
            "name": "RobopayEscrow",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": escrow_address,
        },
        "message": {
            "id": escrow_id,
            "payee": escrow["payee"],
            "token": escrow["token"],
            "amount": escrow["amount"],
            "deadline": escrow["deadline"],
            "terms": bytes.fromhex(escrow["terms"].removeprefix("0x")),
        },
    }


def sign_release(private_key: str, chain_id: int, escrow_address: str,
                 escrow: dict, escrow_id: bytes) -> bytes:
    msg = build_release_message(chain_id, escrow_address, escrow, escrow_id)
    signable = encode_typed_data(full_message=msg)
    signed = Account.sign_message(signable, private_key=private_key)
    return signed.signature


def release_digest(chain_id: int, escrow_address: str, escrow: dict,
                   escrow_id: bytes) -> bytes:
    msg = build_release_message(chain_id, escrow_address, escrow, escrow_id)
    signable = encode_typed_data(full_message=msg)
    from eth_utils import keccak
    return keccak(b"\x19" + signable.version + signable.header + signable.body)