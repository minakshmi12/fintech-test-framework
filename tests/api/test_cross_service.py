"""Transaction Service -> (async event) -> Notification Service."""
import pytest

from fintech_test_automation.utils.polling import eventually


@pytest.mark.smoke
@pytest.mark.regression
def test_transfer_notifies_sender_and_recipient(data, user, recipient):
    tx = data.create_transaction(user, recipient)

    fetch = lambda u: (lambda: data.notifications.list_for_user(u.id).json())  # noqa: E731
    sent = eventually(fetch(user), bool, "sender notification")
    received = eventually(fetch(recipient), bool, "recipient notification")

    assert (sent[0]["type"], sent[0]["transactionId"]) == ("TRANSACTION_SENT", tx["id"])
    assert (received[0]["type"], received[0]["transactionId"]) == ("TRANSACTION_RECEIVED", tx["id"])


@pytest.mark.regression
def test_deposits_do_not_notify(data, user):
    data.create_transaction(user, type="deposit")
    with pytest.raises(AssertionError):
        eventually(lambda: data.notifications.list_for_user(user.id).json(), bool, "unexpected notification", timeout=1.0)
