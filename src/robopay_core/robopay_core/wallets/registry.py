"""Persist wallets to disk as encrypted files, and load them back.

Each wallet is one JSON file under ~/.robopay/wallets/<address>.json containing
the encrypted private key (salt + ciphertext) plus non-secret metadata. Files
are written 0600 (owner-only) as defense-in-depth on top of the encryption.
"""
import json
import os
from pathlib import Path

from .keystore import decrypt_private_key, encrypt_private_key

DEFAULT_DIR = Path.home() / ".robopay" / "wallets"


class WalletRegistry:
    def __init__(self, directory: Path | None = None) -> None:
        self.dir = Path(directory) if directory else DEFAULT_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, address: str) -> Path:
        return self.dir / f"{address}.json"

    def save(self, address: str, private_key: str, passphrase: str,
             label: str = "") -> None:
        blob = encrypt_private_key(private_key, passphrase)
        record = {"address": address, "label": label, "keystore": blob}
        path = self._path(address)
        path.write_text(json.dumps(record, indent=2))
        os.chmod(path, 0o600)

    def load_private_key(self, address: str, passphrase: str) -> str:
        path = self._path(address)
        if not path.exists():
            raise FileNotFoundError(f"No wallet stored for {address}")
        record = json.loads(path.read_text())
        return decrypt_private_key(record["keystore"], passphrase)

    def list_wallets(self) -> list[dict]:
        out = []
        for f in sorted(self.dir.glob("*.json")):
            record = json.loads(f.read_text())
            out.append({"address": record["address"], "label": record.get("label", "")})
        return out

    def exists(self, address: str) -> bool:
        return self._path(address).exists()