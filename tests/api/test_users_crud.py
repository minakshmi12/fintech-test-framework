"""CRUD operations on /api/users."""
import pytest

from fintech_test_automation.assertions import assert_error, assert_status, assert_user
from fintech_test_automation.data.factories import build_user, unknown_id


@pytest.mark.smoke
@pytest.mark.regression
def test_create_user(data):
    payload = {"name": "John Doe", "email": "john@example.com", "accountType": "premium"}
    payload["email"] = build_user()["email"]  # unique, so re-runs and shared envs don't collide

    res = data.users.create(payload)
    assert_status(res, 201)
    body = res.json()
    data.track(body["id"])
    assert_user(body, payload)


@pytest.mark.smoke
@pytest.mark.regression
def test_read_user_returns_what_was_created(data):
    created = data.create_user(accountType="premium")
    res = data.users.get(created.id)
    assert_status(res, 200)
    assert_user(res.json(), {"id": created.id, "name": created.name, "email": created.email, "accountType": "premium"})


@pytest.mark.regression
def test_update_user_persists_changes(data, user):
    res = data.users.update(user.id, {"name": "Renamed Person", "accountType": "business"})
    assert_status(res, 200)
    assert_user(res.json(), {"id": user.id, "name": "Renamed Person", "accountType": "business"})

    persisted = data.users.get(user.id).json()
    assert persisted["name"] == "Renamed Person" and persisted["accountType"] == "business"
    assert persisted["email"] == user.email  # untouched


@pytest.mark.regression
def test_delete_user_then_it_is_gone(data):
    created = data.create_user()
    assert_status(data.users.delete(created.id), 204)
    assert_error(data.users.get(created.id), 404, "USER_NOT_FOUND")
    assert_error(data.users.delete(created.id), 404, "USER_NOT_FOUND")


@pytest.mark.regression
def test_account_type_defaults_to_basic(data):
    res = data.users.create(build_user(accountType=None))
    assert_status(res, 201)
    data.track(res.json()["id"])
    assert res.json()["accountType"] == "basic"


@pytest.mark.regression
@pytest.mark.parametrize("account_type", ["basic", "premium", "business"])
def test_every_account_type_can_be_created(data, account_type):
    assert data.create_user(accountType=account_type).account_type == account_type


@pytest.mark.regression
def test_unknown_user_returns_404(data):
    for call in (data.users.get, data.users.delete):
        assert_error(call(unknown_id()), 404, "USER_NOT_FOUND")
    assert_error(data.users.update(unknown_id(), {"name": "x"}), 404, "USER_NOT_FOUND")


@pytest.mark.regression
def test_responses_never_expose_sensitive_fields(data, user):
    body = data.users.get(user.id).json()
    assert not {"password", "passwordHash", "token"} & set(body)
