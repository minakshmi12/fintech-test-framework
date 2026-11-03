from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import APIRequestContext

from fintech_test_automation.api_log import ApiLogger
from fintech_test_automation.assertions import assert_status
from fintech_test_automation.clients.services import NotificationClient, TransactionClient, UserClient
from fintech_test_automation.data.factories import build_transaction, build_user


@dataclass
class TestUser:
    """A user created for a test, as returned by the API."""

    __test__ = False  # not a pytest class
    id: str
    name: str
    email: str
    account_type: str


class TestDataManager:
    """Creates data through the real API, tracks it, and removes it afterwards (always, even on failure)."""
    __test__ = False

    def __init__(self, request: APIRequestContext, token: str, logger: ApiLogger | None = None):
        self.users = UserClient(request, token, logger)
        self.transactions = TransactionClient(request, token, logger)
        self.notifications = NotificationClient(request, token, logger)
        self._created: list[str] = []

    def create_user(self, **overrides: Any) -> TestUser:
        """Create a unique user via the API (fields overridable) and track it for clean-up."""
        res = self.users.create(build_user(**overrides))
        assert_status(res, 201, "test-data setup: create user")
        body = res.json()
        self._created.append(body["id"])
        return TestUser(body["id"], body["name"], body["email"], body["accountType"])

    def track(self, user_id: str) -> None:
        """Register a user created outside the manager (e.g. through the UI) for clean-up."""
        self._created.append(user_id)

    def create_transaction(self, user: TestUser, recipient: TestUser | None = None, **overrides: Any) -> dict:
        """Create a transaction for a user via the API and return the response body."""
        res = self.transactions.create(build_transaction(user.id, recipient.id if recipient else None, **overrides))
        assert_status(res, 201, "test-data setup: create transaction")
        return res.json()

    def cleanup(self) -> None:
        """Best-effort; must never mask the real test failure."""
        for user_id in reversed(self._created):
            try:
                self.users.delete(user_id)
            except Exception:  # noqa: BLE001
                pass
        self._created.clear()
