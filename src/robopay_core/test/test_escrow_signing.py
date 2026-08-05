import os
import time

import pytest
from eth_account import Account
from web3 import Web3
from web3.logs import DISCARD

from robopay_core.chain_client import ChainClient
from robopay_core.chains import token_address
from robopay_core.erc20_abi import ERC20_ABI
from robopay_core.escrow_client import EscrowClient
from robopay_core.escrow_signing import release_digest, sign_release
from robopay_core.wallets.self_custody import SelfCustodyProvider

DEV_ADDR = os.getenv("ROBOPAY_TEST_ADDRESS", "")
DEV_PASS = os.getenv("ROBOPAY_TEST_PASSPHRASE", "")
CHAIN = "base-sepolia"
CHAIN_ID = 84532
AMOUNT = 100_000

pytestmark = pytest.mark.skipif(
    not DEV_ADDR, reason="set ROBOPAY_TEST_ADDRESS to run the live signing test"
)


@pytest.fixture(scope="module")
def ctx():
    cc = ChainClient(CHAIN)
    ec = EscrowClient(cc, CHAIN)
    wallet = SelfCustodyProvider()
    wallet.load(DEV_ADDR, DEV_PASS)
    return {
        "w3": cc.w3,
        "escrow": ec,
        "wallet": wallet,
        "pk": wallet.private_key(),
        "me": Web3.to_checksum_address(DEV_ADDR),
        "usdc": Web3.to_checksum_address(token_address(CHAIN, "USDC")),
    }


def _send(w3, pk, tx):
    signed = Account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)


@pytest.fixture(scope="module")
def open_escrow(ctx):
    w3, ec, pk, me, usdc = ctx["w3"], ctx["escrow"], ctx["pk"], ctx["me"], ctx["usdc"]
    token = w3.eth.contract(address=usdc, abi=ERC20_ABI)


    current = token.functions.allowance(me, ec.address).call()
    if current < AMOUNT:
        approve_amount = 10_000_000
        receipt = _send(w3, pk, token.functions.approve(
            ec.address, approve_amount
        ).build_transaction({
            "from": me,
            "nonce": w3.eth.get_transaction_count(me),
            "chainId": CHAIN_ID,
        }))
        assert receipt["status"] == 1, "approve transaction failed"
        print(f"\n  approved {approve_amount} (was {current})")
    else:
        print(f"\n  allowance already sufficient: {current}")


    deadline = int(time.time()) + 3600
    terms = Web3.keccak(text="digest-check-terms")
    receipt = _send(w3, pk, ec.contract.functions.open(
        me, usdc, AMOUNT, deadline, terms, int(time.time())
    ).build_transaction({
        "from": me,
        "nonce": w3.eth.get_transaction_count(me),
        "chainId": CHAIN_ID,
        "gas": 300_000,
    }))
    assert receipt["status"] == 1, "open transaction failed"

    events = ec.contract.events.Opened().process_receipt(receipt, errors=DISCARD)
    assert events, "no Opened event found in receipt"
    escrow_id = events[0]["args"]["id"]
    print(f"  opened escrow: 0x{escrow_id.hex()}")
    return escrow_id


def test_escrow_is_locked_on_chain(ctx, open_escrow):
    ec = ctx["escrow"]
    state = None
    for _ in range(10):
        state = ec.get_escrow(open_escrow)
        if state["state"] == "locked":
            break
        time.sleep(1)

    assert state["state"] == "locked", f"escrow never appeared as locked: {state}"
    assert state["amount"] == AMOUNT
    assert state["payer"] == ctx["me"]


def test_python_digest_matches_contract_digest(ctx, open_escrow):
    ec = ctx["escrow"]

    onchain = ec.release_digest(open_escrow)
    escrow_state = ec.get_escrow(open_escrow)
    local = release_digest(CHAIN_ID, ec.address, escrow_state, open_escrow)

    print(f"\n  contract digest: 0x{onchain.hex()}")
    print(f"  python   digest: 0x{local.hex()}")
    print(f"  {'MATCH' if onchain == local else 'MISMATCH'}")

    assert onchain == local, "Python digest differs from the contract's"


def test_signature_recovers_to_signer(ctx, open_escrow):
    ec = ctx["escrow"]
    escrow_state = ec.get_escrow(open_escrow)

    signature = sign_release(ctx["pk"], CHAIN_ID, ec.address,
                             escrow_state, open_escrow)
    assert len(signature) == 65

    digest = ec.release_digest(open_escrow)
    recovered = Account._recover_hash(digest, signature=signature)

    print(f"\n  expected signer : {ctx['me']}")
    print(f"  recovered signer: {recovered}")
    assert Web3.to_checksum_address(recovered) == ctx["me"]