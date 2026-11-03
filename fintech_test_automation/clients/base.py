from __future__ import annotations

import time
from typing import Any

from playwright.sync_api import APIRequestContext, APIResponse

from fintech_test_automation.api_log import ApiLogger


class BaseClient:
    """Playwright APIRequestContext wrapper. Every call is logged; paths are relative to the API root."""

    def __init__(self, request: APIRequestContext, token: str | None = None, logger: ApiLogger | None = None):
        self._request = request
        self._token = token
        self._logger = logger

    def with_token(self, token: str | None):
        """Same client, different credentials. `None` = anonymous (no Authorization header)."""
        return type(self)(self._request, token, self._logger)

    def anonymous(self):
        """Same client without credentials."""
        return self.with_token(None)

    def _send(self, method: str, path: str, data: Any = None, extra_headers: dict[str, str] | None = None) -> APIResponse:
        """Send a request relative to the API root, log it, and return the response."""
        headers = dict(extra_headers or {})
        if self._token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self._token}"
        started = time.monotonic()
        response = self._request.fetch(path, method=method, headers=headers, data=data)
        if self._logger:
            self._logger.record(method=method, url=response.url, headers=headers, request_body=data,
                                status=response.status, response_body=response.text(), started=started)
        return response
