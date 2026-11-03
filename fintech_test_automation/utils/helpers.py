"""Small reusable helpers."""
from __future__ import annotations

import re
from decimal import Decimal


def money(value: float | str | Decimal) -> str:
    """Format like the UI does: 1234.5 -> '$1234.50'."""
    return f"${Decimal(str(value)).quantize(Decimal('0.01'))}"


def find_by_id(items: list[dict], item_id: str) -> dict | None:
    return next((i for i in items if i.get("id") == item_id), None)


def uuid_like(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", value))
