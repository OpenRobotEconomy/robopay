"""Passphrase acquisition"""
import getpass
import os
import stat
import sys
from pathlib import Path

ENV_VAR = "ROBOPAY_PASSPHRASE"
ENV_FILE = "ROBOPAY_PASSPHRASE_FILE"


class PassphraseUnavailable(RuntimeError):
    """No passphrase could be obtained (headless with nothing configured)"""


def _from_file() -> str:
    path = os.getenv(ENV_FILE, "")
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.exists():
        raise PassphraseUnavailable(f"{ENV_FILE} points at a missing file: {p}")
    mode = p.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PassphraseUnavailable(
            f"{p} is readable by other users. Run: chmod 600 {p}")
    return p.read_text().strip()


def get_passphrase(prompt: str = "robopay wallet passphrase: ") -> str:
    from_file = _from_file()
    if from_file:
        return from_file

    from_env = os.getenv(ENV_VAR, "")
    if from_env:
        return from_env

    if sys.stdin.isatty():
        try:
            value = getpass.getpass(prompt)
        except (EOFError, KeyboardInterrupt):
            raise PassphraseUnavailable("passphrase entry cancelled") from None
        if not value:
            raise PassphraseUnavailable("empty passphrase")
        return value

    raise PassphraseUnavailable(
        "no passphrase available. Set ROBOPAY_PASSPHRASE, or "
        "ROBOPAY_PASSPHRASE_FILE to a 0600 file, or run with a terminal.")


def prompt_new_passphrase() -> str:
    if not sys.stdin.isatty():
        value = os.getenv(ENV_VAR, "")
        if value:
            return value
        raise PassphraseUnavailable(
            "creating a wallet needs a passphrase; set ROBOPAY_PASSPHRASE "
            "or run with a terminal attached.")

    while True:
        first = getpass.getpass("choose a wallet passphrase: ")
        if not first:
            print("passphrase cannot be empty.")
            continue
        second = getpass.getpass("confirm passphrase: ")
        if first != second:
            print("passphrases did not match - try again.")
            continue
        return first