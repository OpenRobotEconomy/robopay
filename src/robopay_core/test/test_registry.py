import pytest

from robopay_core.wallets.registry import WalletRegistry
from robopay_core.wallets.self_custody import SelfCustodyProvider

PASS = "test-passphrase"


def test_save_and_load_round_trip(tmp_path):
    reg = WalletRegistry(tmp_path)
    w = SelfCustodyProvider(registry=reg)
    addr = w.create(label="bot-1", passphrase=PASS)

    w2 = SelfCustodyProvider(registry=reg)
    loaded = w2.load(addr, PASS)
    assert loaded == addr
    assert w2.private_key() == w.private_key()


def test_file_is_locked_down(tmp_path):
    reg = WalletRegistry(tmp_path)
    w = SelfCustodyProvider(registry=reg)
    addr = w.create(passphrase=PASS)
    path = tmp_path / f"{addr}.json"
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_stored_file_has_no_plaintext_key(tmp_path):
    reg = WalletRegistry(tmp_path)
    w = SelfCustodyProvider(registry=reg)
    addr = w.create(passphrase=PASS)
    raw = (tmp_path / f"{addr}.json").read_text()
    assert w.private_key()[2:] not in raw


def test_wrong_passphrase_cannot_load(tmp_path):
    reg = WalletRegistry(tmp_path)
    addr = SelfCustodyProvider(registry=reg).create(passphrase=PASS)
    with pytest.raises(ValueError):
        SelfCustodyProvider(registry=reg).load(addr, "wrong")


def test_list_wallets(tmp_path):
    reg = WalletRegistry(tmp_path)
    SelfCustodyProvider(registry=reg).create(label="a", passphrase=PASS)
    SelfCustodyProvider(registry=reg).create(label="b", passphrase=PASS)
    wallets = reg.list_wallets()
    assert len(wallets) == 2
    assert {w["label"] for w in wallets} == {"a", "b"}