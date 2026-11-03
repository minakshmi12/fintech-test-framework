"""Authentication (who are you?) and authorization (what may you do?)."""
import pytest

from fintech_test_automation.assertions import assert_error, assert_status
from fintech_test_automation.data.factories import build_transaction, build_user, unknown_id

pytestmark = [pytest.mark.auth, pytest.mark.regression]


def _calls(data, user, recipient):
    """Every endpoint, as (label, callable(client)) so each case can run with any credentials."""
    return {
        "POST /users": lambda c: c["users"].create(build_user()),
        "GET /users/:id": lambda c: c["users"].get(user.id),
        "PUT /users/:id": lambda c: c["users"].update(user.id, {"name": "x"}),
        "DELETE /users/:id": lambda c: c["users"].delete(unknown_id()),
        "POST /transactions": lambda c: c["tx"].create(build_transaction(user.id, recipient.id)),
        "GET /transactions/:userId": lambda c: c["tx"].list_for_user(user.id),
    }


def _clients(data, token):
    return {"users": data.users.with_token(token), "tx": data.transactions.with_token(token)}


ENDPOINTS = ["POST /users", "GET /users/:id", "PUT /users/:id", "DELETE /users/:id",
             "POST /transactions", "GET /transactions/:userId"]


@pytest.mark.smoke
@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_requests_without_credentials_get_401(data, user, recipient, endpoint):
    assert_error(_calls(data, user, recipient)[endpoint](_clients(data, None)), 401, "UNAUTHORIZED")


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_invalid_token_gets_401(data, user, recipient, endpoint):
    res = _calls(data, user, recipient)[endpoint](_clients(data, "not-a-real-token"))
    assert_error(res, 401, "UNAUTHORIZED")


@pytest.mark.parametrize("header", ["Basic YWRtaW46YWRtaW4=", "Bearer", "admin-token", "Bearer  "])
def test_malformed_authorization_headers_get_401(data, user, header):
    res = data.users._send("GET", f"users/{user.id}", extra_headers={"Authorization": header})
    assert_error(res, 401, "UNAUTHORIZED")


@pytest.mark.smoke
def test_read_only_token_can_read(data, user, recipient, readonly_token):
    c = _clients(data, readonly_token)
    assert_status(c["users"].get(user.id), 200)
    assert_status(c["tx"].list_for_user(user.id), 200)


@pytest.mark.parametrize("endpoint", ["POST /users", "PUT /users/:id", "DELETE /users/:id", "POST /transactions"])
def test_read_only_token_cannot_write(data, user, recipient, readonly_token, endpoint):
    res = _calls(data, user, recipient)[endpoint](_clients(data, readonly_token))
    assert_error(res, 403, "FORBIDDEN")


def test_forbidden_write_has_no_side_effects(data, user, recipient, readonly_token):
    ro_users, ro_tx = data.users.with_token(readonly_token), data.transactions.with_token(readonly_token)
    ro_users.delete(user.id)
    ro_users.update(user.id, {"name": "Hacked"})
    ro_tx.create(build_transaction(user.id, recipient.id))

    assert data.users.get(user.id).json()["name"] == user.name
    assert data.transactions.list_for_user(user.id).json() == []


def test_authentication_is_checked_before_validation(data):
    """An anonymous caller must not learn anything about validation rules."""
    assert_error(data.users.anonymous().create({}), 401, "UNAUTHORIZED")


def test_error_responses_do_not_leak_the_token(data, admin_token):
    res = data.users.get(unknown_id())
    assert admin_token not in res.text()
