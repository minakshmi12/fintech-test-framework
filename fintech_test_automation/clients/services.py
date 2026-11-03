from __future__ import annotations

from typing import Any

from playwright.sync_api import APIResponse

from .base import BaseClient


class UserClient(BaseClient):
    """API client for the User service (/users)."""

    def create(self, payload: dict[str, Any]) -> APIResponse:
        """POST /users: create a user."""
        return self._send("POST", "users", payload)

    def create_raw(self, raw_body: str) -> APIResponse:
        """Send an arbitrary (possibly malformed) body with a JSON content type."""
        return self._send("POST", "users", raw_body, {"Content-Type": "application/json"})

    def get(self, user_id: str) -> APIResponse:
        """GET /users/:id: fetch a user."""
        return self._send("GET", f"users/{user_id}")

    def update(self, user_id: str, payload: dict[str, Any]) -> APIResponse:
        """PUT /users/:id: update a user."""
        return self._send("PUT", f"users/{user_id}", payload)

    def delete(self, user_id: str) -> APIResponse:
        """DELETE /users/:id: delete a user."""
        return self._send("DELETE", f"users/{user_id}")


class TransactionClient(BaseClient):
    """API client for the Transaction service (/transactions)."""

    def create(self, payload: dict[str, Any]) -> APIResponse:
        """POST /transactions: create a transfer, deposit or withdrawal."""
        return self._send("POST", "transactions", payload)

    def list_for_user(self, user_id: str) -> APIResponse:
        """GET /transactions/:userId: sent and received transactions, newest first."""
        return self._send("GET", f"transactions/{user_id}")


class NotificationClient(BaseClient):
    """API client for the Notification service (/notifications)."""

    def list_for_user(self, user_id: str) -> APIResponse:
        """GET /notifications/:userId: notifications generated for a user."""
        return self._send("GET", f"notifications/{user_id}")
