import pytest

from fintech_test_automation.pages.registration_page import RegistrationPage
from fintech_test_automation.pages.transactions_page import TransactionsPage


@pytest.fixture(autouse=True)
def _apply_env_timeouts(page, env):
    page.set_default_timeout(env.timeout_ms)


@pytest.fixture
def registration_page(page):
    return RegistrationPage(page)


@pytest.fixture
def transactions_page(page):
    return TransactionsPage(page)
