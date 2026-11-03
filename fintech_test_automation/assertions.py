"""Custom assertions: domain-aware checks whose failure messages include the response that caused them."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from playwright.sync_api import APIResponse

USER_FIELDS = {"id", "name", "email", "accountType", "createdAt"}
TRANSACTION_FIELDS = {"id", "userId", "amount", "type", "recipientId", "status", "createdAt"}


def _describe(res: APIResponse) -> str:
    text = res.text()
    return f"{res.request.method} {res.url} -> {res.status}\n  body: {text[:500]}"


def assert_status(res: APIResponse, expected: int, context: str = "") -> None:
    assert res.status == expected, f"{context + ': ' if context else ''}expected HTTP {expected}\n{_describe(res)}"


def assert_iso_timestamp(value: Any) -> None:
    assert isinstance(value, str), f"timestamp must be a string, got {value!r}"
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise AssertionError(f"not an ISO-8601 timestamp: {value!r}") from None


def assert_amount(actual: float, expected: float | str | Decimal) -> None:
    """Money is compared as Decimal to 2 places, never as raw floats."""
    a, e = Decimal(str(actual)).quantize(Decimal("0.01")), Decimal(str(expected)).quantize(Decimal("0.01"))
    assert a == e, f"amount mismatch: got {a}, expected {e}"


def assert_error(res: APIResponse, status: int, code: str | None = None, field: str | None = None) -> dict:
    """Assert the standard error envelope: {"error": {"code", "message", "details": [{"field", "message"}]}}."""
    assert_status(res, status)
    err = res.json().get("error")
    assert err, f"missing error envelope\n{_describe(res)}"
    assert err.get("code") and err.get("message"), f"error needs code and message: {err}"
    if code:
        assert err["code"] == code, f"expected error code {code}, got {err['code']}"
    if field:
        fields = [d["field"] for d in err.get("details", [])]
        assert field in fields, f"expected a validation error on '{field}', got {fields}"
    return err


def assert_user(body: dict, expected: dict | None = None) -> None:
    """Contract check for a User resource, plus optional expected field values."""
    assert set(body) == USER_FIELDS, f"unexpected user fields: {sorted(set(body) ^ USER_FIELDS)}"
    assert isinstance(body["id"], str) and body["id"]
    assert_iso_timestamp(body["createdAt"])
    for key, value in (expected or {}).items():
        actual = body[key].lower() if key == "email" and isinstance(body[key], str) else body[key]
        want = value.lower() if key == "email" else value
        assert actual == want, f"user.{key}: expected {want!r}, got {actual!r}"


def assert_transaction(body: dict, expected: dict | None = None) -> None:
    assert set(body) == TRANSACTION_FIELDS, f"unexpected transaction fields: {sorted(set(body) ^ TRANSACTION_FIELDS)}"
    assert body["status"] in {"completed", "pending"}
    assert_iso_timestamp(body["createdAt"])
    for key, value in (expected or {}).items():
        if key == "amount":
            assert_amount(body["amount"], value)
        else:
            assert body[key] == value, f"transaction.{key}: expected {value!r}, got {body[key]!r}"


def assert_newest_first(items: list[dict], key: str = "createdAt") -> None:
    stamps = [i[key] for i in items]
    assert stamps == sorted(stamps, reverse=True), f"not sorted newest-first: {stamps}"
