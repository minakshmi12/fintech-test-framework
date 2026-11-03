"""Fintech test automation (pytest + Playwright): API and UI tests for a User/Transaction/Notification platform.

Selects the environment (--env / TEST_ENV), starts the mock platform for `local`, and provides shared fixtures and reporting.
"""
from __future__ import annotations

import os
import threading

import pytest
from playwright.sync_api import Playwright

from config.settings import EnvConfig, get_config
from fintech_test_automation.api_log import ApiLogger
from fintech_test_automation.data.factories import RUN_ID
from fintech_test_automation.data.manager import TestDataManager

pytest_plugins = ["fintech_test_automation.reporting"]

_mock_server = None


# ----------------------------- CLI / environment -----------------------------
def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None, help="local | qa | staging (default: $TEST_ENV or local)")


def pytest_configure(config):
    if config.getoption("--env"):
        os.environ["TEST_ENV"] = config.getoption("--env")
    try:
        env = get_config()
    except ValueError as e:
        raise pytest.UsageError(str(e))
    if hasattr(config.option, "reruns") and not config.option.reruns:
        config.option.reruns = env.reruns  # per-environment flaky-test retries

    # The mock platform starts once, in the main process; xdist workers share it.
    global _mock_server
    if env.start_mock_server and not hasattr(config, "workerinput"):
        from werkzeug.serving import make_server
        from mock_services.app import create_app
        host, _, port = env.base_url.split("//")[-1].partition(":")
        if not port.isdigit():
            raise pytest.UsageError(
                f"The local mock server needs a BASE_URL like http://127.0.0.1:4000, got '{env.base_url}'. "
                "Remove the BASE_URL/API_URL overrides (e.g. in .env) when using TEST_ENV=local.")
        _mock_server = make_server(host, int(port), create_app(), threaded=True)
        threading.Thread(target=_mock_server.serve_forever, daemon=True).start()


def pytest_unconfigure(config):
    if _mock_server:
        _mock_server.shutdown()


def pytest_report_header(config):
    env = get_config()
    return f"environment: {env.name} | base_url: {env.base_url} | run_id: {RUN_ID}"


def pytest_collection_modifyitems(items):
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        item.add_marker(pytest.mark.ui if "/tests/ui/" in path else pytest.mark.api)


# --------------------------------- fixtures ---------------------------------
@pytest.fixture(scope="session")
def env() -> EnvConfig:
    return get_config()


@pytest.fixture(scope="session")
def base_url(env) -> str:
    """Overrides pytest-playwright's base_url so UI tests follow the selected environment."""
    return env.base_url


@pytest.fixture(scope="session")
def admin_token(env) -> str:
    if not env.api_token:
        pytest.fail(f"No API token for '{env.name}'. Set the API_TOKEN environment variable.", pytrace=False)
    return env.api_token


@pytest.fixture
def readonly_token(env) -> str:
    if not env.readonly_token:
        pytest.skip(f"READONLY_TOKEN is not configured for '{env.name}'")
    return env.readonly_token


@pytest.fixture
def api_log(request):
    """Collects every API call made during the test; flushed to disk and attached to failures."""
    logger = ApiLogger(request.node.nodeid)
    request.node.api_log = logger
    yield logger
    logger.flush()


@pytest.fixture
def api_request(playwright: Playwright, env):
    ctx = playwright.request.new_context(
        base_url=env.api_url, extra_http_headers={"Accept": "application/json"}, timeout=env.timeout_ms * 3)
    yield ctx
    ctx.dispose()


@pytest.fixture
def data(api_request, admin_token, api_log) -> TestDataManager:
    manager = TestDataManager(api_request, admin_token, api_log)
    yield manager
    manager.cleanup()  # always removes what the test created


@pytest.fixture
def user(data):
    """A basic-account user."""
    return data.create_user()


@pytest.fixture
def recipient(data):
    return data.create_user()
