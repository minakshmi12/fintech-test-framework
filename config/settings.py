"""Per-environment configuration. Select with TEST_ENV=local|qa|staging (or `pytest --env=qa`)."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class EnvConfig:
    """Settings for one target environment (URLs, tokens, timeouts, rerun policy)."""

    name: str
    base_url: str                  # gateway origin (UI + API)
    api_url: str                   # API root, always ends with "/"
    start_mock_server: bool        # spin up the in-repo mock platform for this run
    timeout_ms: int                # default Playwright timeout
    reruns: int                    # flaky-test retries
    api_token: str | None = None       # full-access token   (env: API_TOKEN)
    readonly_token: str | None = None  # GET-only token       (env: READONLY_TOKEN)


ENVIRONMENTS: dict[str, EnvConfig] = {
    "local": EnvConfig("local", "http://127.0.0.1:4000", "http://127.0.0.1:4000/api/",
                       start_mock_server=True, timeout_ms=5_000, reruns=0,
                       api_token="admin-token", readonly_token="readonly-token"),
    "qa": EnvConfig("qa", "https://qa-gateway.example.com", "https://qa-gateway.example.com/api/",
                    start_mock_server=False, timeout_ms=10_000, reruns=1),
    "staging": EnvConfig("staging", "https://staging-gateway.example.com",
                         "https://staging-gateway.example.com/api/",
                         start_mock_server=False, timeout_ms=15_000, reruns=2),
}


def get_config(name: str | None = None) -> EnvConfig:
    name = (name or os.getenv("TEST_ENV", "local")).lower()
    if name not in ENVIRONMENTS:
        raise ValueError(f"Unknown TEST_ENV '{name}'. Valid: {', '.join(ENVIRONMENTS)}")
    cfg = ENVIRONMENTS[name]
    base = os.getenv("BASE_URL", cfg.base_url).rstrip("/")
    api = os.getenv("API_URL", f"{base}/api").rstrip("/") + "/"
    return replace(cfg, base_url=base, api_url=api,
                   api_token=os.getenv("API_TOKEN", cfg.api_token),
                   readonly_token=os.getenv("READONLY_TOKEN", cfg.readonly_token))
