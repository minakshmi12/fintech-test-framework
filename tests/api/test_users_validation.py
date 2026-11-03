"""Data validation + error-scenario handling for /api/users."""
import pytest

from fintech_test_automation.assertions import assert_error, assert_status
from fintech_test_automation.data.factories import build_user, invalid_user_payloads

pytestmark = [pytest.mark.regression, pytest.mark.validation]


@pytest.mark.parametrize("case,payload,field", invalid_user_payloads(), ids=lambda v: v if isinstance(v, str) else "")
def test_invalid_payload_is_rejected_with_field_detail(data, case, payload, field):
    assert_error(data.users.create(payload), 400, "VALIDATION", field=field)


def test_all_problems_are_reported_together(data):
    err = assert_error(data.users.create({}), 400, "VALIDATION")
    assert {"name", "email"} <= {d["field"] for d in err["details"]}


@pytest.mark.parametrize("raw", ["{not json", "", "[]", '"just a string"', "null"])
def test_malformed_or_non_object_json_is_rejected(data, raw):
    assert_error(data.users.create_raw(raw), 400, "INVALID_JSON")


def test_duplicate_email_is_rejected_case_insensitively(data, user):
    assert_error(data.users.create(build_user(email=user.email)), 409, "DUPLICATE_EMAIL")
    assert_error(data.users.create(build_user(email=user.email.upper())), 409, "DUPLICATE_EMAIL")


def test_email_is_normalised_to_lowercase(data):
    payload = build_user()
    payload["email"] = payload["email"].upper()
    res = data.users.create(payload)
    assert_status(res, 201)
    data.track(res.json()["id"])
    assert res.json()["email"] == payload["email"].lower()


def test_name_length_boundary(data):
    ok = data.users.create(build_user(name="x" * 100))
    assert_status(ok, 201)
    data.track(ok.json()["id"])
    assert_error(data.users.create(build_user(name="x" * 101)), 400, "VALIDATION", "name")


def test_email_cannot_be_changed_by_update(data, user):
    assert_error(data.users.update(user.id, {"email": "new@example.com"}), 400, "VALIDATION", "email")


def test_update_validates_account_type(data, user):
    assert_error(data.users.update(user.id, {"accountType": "gold"}), 400, "VALIDATION", "accountType")


def test_failed_create_does_not_create_a_user(data, user):
    before = data.users.get(user.id).json()
    data.users.create(build_user(email=user.email))  # rejected as duplicate
    assert data.users.get(user.id).json() == before
