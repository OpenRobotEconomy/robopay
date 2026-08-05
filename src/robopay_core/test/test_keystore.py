import pytest

from robopay_core.wallets.keystore import decrypt_private_key, encrypt_private_key

KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
PASS = "correct horse battery staple"


def test_round_trip():
    blob = encrypt_private_key(KEY, PASS)
    assert decrypt_private_key(blob, PASS) == KEY


def test_ciphertext_does_not_contain_the_key():
    blob = encrypt_private_key(KEY, PASS)
    assert KEY not in blob["ciphertext"]
    assert KEY[2:] not in blob["ciphertext"]


def test_wrong_passphrase_raises():
    blob = encrypt_private_key(KEY, PASS)
    with pytest.raises(ValueError):
        decrypt_private_key(blob, "wrong passphrase")


def test_same_key_encrypts_differently_each_time():
    a = encrypt_private_key(KEY, PASS)
    b = encrypt_private_key(KEY, PASS)
    assert a["ciphertext"] != b["ciphertext"]
    assert a["salt"] != b["salt"]


def test_tampered_ciphertext_raises():
    blob = encrypt_private_key(KEY, PASS)
    blob["ciphertext"] = blob["ciphertext"][:-4] + "AAAA"
    with pytest.raises(ValueError):
        decrypt_private_key(blob, PASS)