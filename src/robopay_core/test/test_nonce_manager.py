from unittest.mock import MagicMock

from robopay_core.nonce_manager import NonceManager


def _w3_saying(nonce):
    w3 = MagicMock()
    w3.eth.get_transaction_count.return_value = nonce
    return w3


def test_seeds_from_chain_on_first_use():
    nm = NonceManager(_w3_saying(7))
    assert nm.next_nonce("0xA") == 7


def test_hands_out_sequential_without_asking_chain_again():
    w3 = _w3_saying(7)
    nm = NonceManager(w3)
    got = [nm.next_nonce("0xA") for _ in range(5)]
    assert got == [7, 8, 9, 10, 11]
    assert w3.eth.get_transaction_count.call_count == 1


def test_separate_wallets_have_separate_counters():
    w3 = MagicMock()
    w3.eth.get_transaction_count.side_effect = lambda addr, _="pending": {
        "0xA": 3, "0xB": 100}[addr]
    nm = NonceManager(w3)
    assert nm.next_nonce("0xA") == 3
    assert nm.next_nonce("0xB") == 100
    assert nm.next_nonce("0xA") == 4


def test_resync_realigns_to_chain():
    w3 = _w3_saying(7)
    nm = NonceManager(w3)
    nm.next_nonce("0xA")
    nm.next_nonce("0xA")
    w3.eth.get_transaction_count.return_value = 5
    assert nm.resync("0xA") == 5
    assert nm.next_nonce("0xA") == 5