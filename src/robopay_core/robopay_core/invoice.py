"""Construct and validate payment requests (invoices).
"""
import uuid
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation

from web3 import Web3

VALID_SETTLEMENTS = ("direct", "escrow")


class InvalidInvoice(ValueError):
    """An invoice was malformed. Never act on one that failed to parse."""


@dataclass
class Invoice:
    request_id: str
    payee_address: str
    amount: str
    asset: str = "USDC"
    memo: str = ""
    settlement: str = "direct"
    terms_hash: str = ""

    @classmethod
    def create(cls, payee: str, amount: str, memo: str = "",
               asset: str = "USDC", settlement: str = "direct",
               terms_hash: str = "", request_id: str = "") -> "Invoice":
        """Build an invoice to send to a payer."""
        inv = cls(
            request_id=request_id or str(uuid.uuid4()),
            payee_address=payee,
            amount=str(amount),
            asset=asset,
            memo=memo,
            settlement=settlement,
            terms_hash=terms_hash,
        )
        inv.validate()
        return inv

    @classmethod
    def parse(cls, data: dict) -> "Invoice":
        try:
            inv = cls(
                request_id=str(data["request_id"]),
                payee_address=str(data["payee_address"]),
                amount=str(data["amount"]),
                asset=str(data.get("asset", "USDC")),
                memo=str(data.get("memo", "")),
                settlement=str(data.get("settlement", "direct")),
                terms_hash=str(data.get("terms_hash", "")),
            )
        except KeyError as e:
            raise InvalidInvoice(f"missing field: {e}") from None
        inv.validate()
        return inv

    def validate(self) -> None:
        if not self.request_id:
            raise InvalidInvoice("request_id is required")

        if not Web3.is_address(self.payee_address):
            raise InvalidInvoice(f"not a valid address: {self.payee_address}")

        try:
            value = Decimal(self.amount)
        except (InvalidOperation, TypeError):
            raise InvalidInvoice(f"amount is not a number: {self.amount}") from None
        if value <= 0:
            raise InvalidInvoice(f"amount must be positive, got {self.amount}")

        if self.settlement not in VALID_SETTLEMENTS:
            raise InvalidInvoice(
                f"settlement must be one of {VALID_SETTLEMENTS}, "
                f"got {self.settlement!r}")

        if self.settlement == "escrow" and not self.terms_hash:
            raise InvalidInvoice("escrow settlement requires a terms_hash")

    def to_dict(self) -> dict:
        return asdict(self)