"""Transactions: creation, retrieval, validation, business rules."""
import pytest

from fintech_test_automation.assertions import assert_amount, assert_error, assert_newest_first, assert_status, assert_transaction
from fintech_test_automation.data.factories import TRANSACTION_LIMITS, build_transaction, invalid_transaction_payloads, unknown_id
from fintech_test_automation.utils.helpers import find_by_id


@pytest.mark.smoke
@pytest.mark.regression
def test_create_transfer(data, user, recipient):
    payload = {"userId": user.id, "amount": 100.50, "type": "transfer", "recipientId": recipient.id}
    res = data.transactions.create(payload)
    assert_status(res, 201)
    assert_transaction(res.json(), {**payload, "status": "completed"})


@pytest.mark.regression
@pytest.mark.parametrize("tx_type", ["deposit", "withdrawal"])
def test_create_non_transfer_types(data, user, tx_type):
    res = data.transactions.create(build_transaction(user.id, type=tx_type, amount=25.00))
    assert_status(res, 201)
    assert_transaction(res.json(), {"type": tx_type, "recipientId": None, "amount": 25.00})


@pytest.mark.smoke
@pytest.mark.regression
def test_user_transactions_are_listed_newest_first(data, user, recipient):
    first = data.create_transaction(user, recipient, amount=10)
    second = data.create_transaction(user, amount=20, type="deposit")

    res = data.transactions.list_for_user(user.id)
    assert_status(res, 200)
    items = res.json()
    assert [t["id"] for t in items][:2] == [second["id"], first["id"]]
    assert_newest_first(items)
    assert_amount(find_by_id(items, first["id"])["amount"], 10)


@pytest.mark.regression
def test_recipient_sees_incoming_transfer(data, user, recipient):
    sent = data.create_transaction(user, recipient)
    assert find_by_id(data.transactions.list_for_user(recipient.id).json(), sent["id"])


@pytest.mark.regression
def test_user_without_transactions_gets_empty_list(data, user):
    res = data.transactions.list_for_user(user.id)
    assert_status(res, 200)
    assert res.json() == []


@pytest.mark.regression
def test_transactions_are_isolated_between_users(data, user, recipient):
    outsider = data.create_user()
    data.create_transaction(user, recipient)
    assert data.transactions.list_for_user(outsider.id).json() == []


@pytest.mark.regression
@pytest.mark.validation
def test_invalid_payloads_are_rejected_with_field_detail(data, user, recipient):
    for case, payload, field in invalid_transaction_payloads(user.id, recipient.id):
        err = assert_error(data.transactions.create(payload), 400, "VALIDATION")
        assert field in {d["field"] for d in err["details"]}, f"{case}: expected error on '{field}', got {err}"


@pytest.mark.regression
def test_rejected_transaction_is_not_recorded(data, user, recipient):
    data.transactions.create(build_transaction(user.id, recipient.id, amount=-1))
    assert data.transactions.list_for_user(user.id).json() == []


@pytest.mark.regression
def test_unknown_user_and_recipient(data, user):
    assert_error(data.transactions.create(build_transaction(unknown_id(), user.id)), 404, "USER_NOT_FOUND")
    assert_error(data.transactions.create(build_transaction(user.id, unknown_id())), 404, "RECIPIENT_NOT_FOUND")
    assert_error(data.transactions.list_for_user(unknown_id()), 404, "USER_NOT_FOUND")


@pytest.mark.regression
@pytest.mark.parametrize("account_type,limit", TRANSACTION_LIMITS.items())
def test_transaction_limit_per_account_type(data, account_type, limit):
    owner = data.create_user(accountType=account_type)
    assert_status(data.transactions.create(build_transaction(owner.id, amount=limit)), 201)          # at the limit
    assert_error(data.transactions.create(build_transaction(owner.id, amount=limit + 0.01)), 422, "LIMIT_EXCEEDED")


@pytest.mark.regression
def test_upgrading_account_raises_the_limit(data, user):
    assert_error(data.transactions.create(build_transaction(user.id, amount=5_000)), 422, "LIMIT_EXCEEDED")
    data.users.update(user.id, {"accountType": "premium"})
    assert_status(data.transactions.create(build_transaction(user.id, amount=5_000)), 201)


@pytest.mark.regression
@pytest.mark.parametrize("amount", [0.01, 99.99, 100.5, 1000])
def test_amount_precision_is_preserved(data, user, amount):
    res = data.transactions.create(build_transaction(user.id, amount=amount))
    assert_status(res, 201)
    assert_amount(res.json()["amount"], amount)
