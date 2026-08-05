"""Encrypt/decrypt a private key with a passphrase, using audited primitives.

Using the `cryptography` library
"""
import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    raw = kdf.derive(passphrase.encode())
    return base64.urlsafe_b64encode(raw)  # Fernet wants a url-safe base64 key


def encrypt_private_key(private_key: str, passphrase: str) -> dict:
    salt = os.urandom(16)
    fernet = Fernet(_derive_key(passphrase, salt))
    token = fernet.encrypt(private_key.encode())
    return {
        "version": 1,
        "salt": base64.b64encode(salt).decode(),
        "ciphertext": token.decode(),
    }


def decrypt_private_key(blob: dict, passphrase: str) -> str:
    salt = base64.b64decode(blob["salt"])
    fernet = Fernet(_derive_key(passphrase, salt))
    try:
        return fernet.decrypt(blob["ciphertext"].encode()).decode()
    except InvalidToken:
        raise ValueError("Wrong passphrase or corrupted keystore.") from None