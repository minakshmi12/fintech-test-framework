"""Test data factories. All data is unique per call and tagged with a run id for easy clean-up."""
from __future__ import annotations

import os
import random
import string
import uuid
from typing import Any

from faker import Faker

fake = Faker()
RUN_ID = os.getenv("RUN_ID") or "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

ACCOUNT_TYPES = ("basic", "premium", "business")
TRANSACTION_LIMITS = {"basic": 1_000, "premium": 10_000, "business": 50_000}


def _rand(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def build_user(**overrides: Any) -> dict[str, Any]:
    """Valid payload for POST /api/users. Pass a key=None... to remove it, e.g. build_user(email=None)."""
    user = {"name": fake.name(), "email": f"qa+{RUN_ID}-{_rand()}@example.com", "accountType": "basic"}
    user.update(overrides)
    return {k: v for k, v in user.items() if v is not None}


def build_amount(low: float = 1, high: float = 100) -> float:
    return round(random.uniform(low, high), 2)


def build_transaction(user_id: str, recipient_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Valid payload for POST /api/transactions (a transfer when recipient_id is given, else a deposit)."""
    tx: dict[str, Any] = {"userId": user_id, "amount": build_amount(),
                          "type": "transfer" if recipient_id else "deposit"}
    if recipient_id:
        tx["recipientId"] = recipient_id
    tx.update(overrides)
    return {k: v for k, v in tx.items() if v is not None}


def unknown_id() -> str:
    return str(uuid.uuid4())


# ---- invalid-payload catalogues for data-driven validation tests: (case id, payload, offending field) ----
def invalid_user_payloads() -> list[tuple[str, dict[str, Any], str]]:
    return [
        ("missing-name", build_user(name=None), "name"),
        ("blank-name", build_user(name="   "), "name"),
        ("name-too-long", build_user(name="x" * 101), "name"),
        ("name-not-a-string", build_user(name=12345), "name"),
        ("missing-email", build_user(email=None), "email"),
        ("email-no-at", build_user(email="john.example.com"), "email"),
        ("email-no-domain", build_user(email="john@"), "email"),
        ("email-with-space", build_user(email="john doe@example.com"), "email"),
        ("email-not-a-string", build_user(email=42), "email"),
        ("unknown-account-type", build_user(accountType="platinum"), "accountType"),
        ("account-type-not-a-string", build_user(accountType=7), "accountType"),
    ]


def invalid_transaction_payloads(user_id: str, recipient_id: str) -> list[tuple[str, dict[str, Any], str]]:
    base = lambda **o: build_transaction(user_id, recipient_id, **o)  # noqa: E731
    return [
        ("missing-user-id", base(userId=None), "userId"),
        ("missing-amount", base(amount=None), "amount"),
        ("zero-amount", base(amount=0), "amount"),
        ("negative-amount", base(amount=-5), "amount"),
        ("amount-as-string", base(amount="100"), "amount"),
        ("amount-as-boolean", base(amount=True), "amount"),
        ("too-many-decimals", base(amount=10.123), "amount"),
        ("missing-type", base(type=None), "type"),
        ("unknown-type", base(type="refund"), "type"),
        ("transfer-without-recipient", base(recipientId=None), "recipientId"),
        ("transfer-to-self", base(recipientId=user_id), "recipientId"),
        ("deposit-with-recipient", base(type="deposit"), "recipientId"),
    ]
