"""User registration flow + its error messages."""
import re

import pytest
from playwright.sync_api import expect

from fintech_test_automation.assertions import assert_status, assert_user
from fintech_test_automation.data.factories import build_user

pytestmark = pytest.mark.regression


@pytest.mark.smoke
def test_user_can_register(data, registration_page):
    user = build_user(accountType="premium")
    registration_page.goto()
    registration_page.register(user["name"], user["email"], "premium")

    expect(registration_page.success).to_contain_text(user["name"])
    new_id = registration_page.created_user_id()
    data.track(new_id)

    # UI result matches backend truth
    res = data.users.get(new_id)
    assert_status(res, 200)
    assert_user(res.json(), {"name": user["name"], "email": user["email"], "accountType": "premium"})


@pytest.mark.parametrize("account_type", ["basic", "premium", "business"])
def test_selected_account_type_is_saved(data, registration_page, account_type):
    user = build_user()
    registration_page.goto()
    registration_page.register(user["name"], user["email"], account_type)
    data.track(registration_page.created_user_id())
    expect(registration_page.page.get_by_test_id("created-type")).to_have_text(account_type)


def test_registration_leads_to_transactions_page(data, registration_page, page):
    user = build_user()
    registration_page.goto()
    registration_page.register(user["name"], user["email"])
    data.track(registration_page.created_user_id())
    registration_page.go_to_transactions()
    expect(page).to_have_url(re.compile(r"/transactions\.html\?userId="))
    expect(page.get_by_test_id("account-summary")).to_contain_text(user["name"])


# ------------------------------- error message validation -------------------------------
@pytest.mark.validation
@pytest.mark.parametrize("name,email,field,message", [
    ("", "ok@example.com", "name", "Name is required"),
    ("   ", "ok@example.com", "name", "Name is required"),
    ("Jane Doe", "", "email", "Enter a valid email address"),
    ("Jane Doe", "not-an-email", "email", "Enter a valid email address"),
    ("Jane Doe", "missing@tld", "email", "Enter a valid email address"),
], ids=["empty-name", "blank-name", "empty-email", "bad-email", "no-tld"])
def test_field_validation_messages(registration_page, name, email, field, message):
    registration_page.goto()
    registration_page.register(name, email)
    expect(registration_page.field_error(field)).to_have_text(message)
    expect(registration_page.success).to_be_hidden()


@pytest.mark.validation
def test_all_field_errors_show_at_once(registration_page):
    registration_page.goto()
    registration_page.register("", "")
    expect(registration_page.field_error("name")).to_be_visible()
    expect(registration_page.field_error("email")).to_be_visible()


@pytest.mark.validation
def test_errors_clear_after_correcting_input(data, registration_page):
    user = build_user()
    registration_page.goto()
    registration_page.register("", user["email"])
    expect(registration_page.field_error("name")).to_be_visible()

    registration_page.register(user["name"], user["email"])
    expect(registration_page.field_error("name")).to_be_hidden()
    data.track(registration_page.created_user_id())


@pytest.mark.validation
def test_duplicate_email_shows_server_error(data, user, registration_page):
    registration_page.goto()
    registration_page.register("Someone Else", user.email)
    expect(registration_page.form_error).to_have_text("Email already registered")
    expect(registration_page.success).to_be_hidden()
