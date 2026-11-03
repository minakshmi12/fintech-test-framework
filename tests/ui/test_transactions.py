"""Transaction creation flow + its error messages."""
import pytest
from playwright.sync_api import expect

from fintech_test_automation.assertions import assert_amount, assert_status
from fintech_test_automation.data.factories import unknown_id

pytestmark = pytest.mark.regression


@pytest.mark.smoke
def test_user_can_send_a_transfer(data, user, recipient, transactions_page):
    transactions_page.goto(user.id)
    expect(transactions_page.summary).to_contain_text(user.name)
    expect(transactions_page.empty).to_be_visible()

    transactions_page.submit(100.50, "transfer", recipient.id)

    expect(transactions_page.success).to_have_text("Transaction completed")
    expect(transactions_page.rows).to_have_count(1)
    expect(transactions_page.rows.first).to_contain_text("Transfer sent")
    expect(transactions_page.rows.first).to_contain_text("$100.50")

    # UI result matches backend truth
    items = data.transactions.list_for_user(user.id).json()
    assert len(items) == 1
    assert_amount(items[0]["amount"], 100.50)
    assert items[0]["recipientId"] == recipient.id


@pytest.mark.parametrize("tx_type,label", [("deposit", "Deposit"), ("withdrawal", "Withdrawal")])
def test_deposit_and_withdrawal_do_not_need_a_recipient(user, transactions_page, tx_type, label):
    transactions_page.goto(user.id)
    transactions_page.page.get_by_test_id("type").select_option(tx_type)
    expect(transactions_page.recipient_group).to_be_hidden()

    transactions_page.submit(40, tx_type)
    expect(transactions_page.success).to_be_visible()
    expect(transactions_page.rows.first).to_contain_text(label)


def test_recipient_sees_the_incoming_transfer(data, user, recipient, transactions_page):
    data.create_transaction(user, recipient, amount=12.34)
    transactions_page.goto(recipient.id)
    expect(transactions_page.rows).to_have_count(1)
    expect(transactions_page.rows.first).to_contain_text("Transfer received")
    expect(transactions_page.rows.first).to_contain_text("$12.34")


def test_history_lists_newest_first(data, user, transactions_page):
    data.create_transaction(user, type="deposit", amount=1)
    data.create_transaction(user, type="deposit", amount=2)
    transactions_page.goto(user.id)
    expect(transactions_page.rows).to_have_count(2)
    expect(transactions_page.rows.first).to_contain_text("$2.00")


def test_end_to_end_register_then_transfer(data, recipient, registration_page, transactions_page, page):
    """Full journey: register a new account in the UI, then send money to an existing user."""
    from fintech_test_automation.data.factories import build_user
    new = build_user(accountType="premium")
    registration_page.goto()
    registration_page.register(new["name"], new["email"], "premium")
    data.track(registration_page.created_user_id())
    registration_page.go_to_transactions()

    expect(transactions_page.summary).to_contain_text("premium account")
    transactions_page.submit(2_500, "transfer", recipient.id)   # above the basic limit, fine for premium
    expect(transactions_page.success).to_be_visible()
    expect(transactions_page.rows).to_have_count(1)
    assert_status(data.transactions.list_for_user(recipient.id), 200)
    assert len(data.transactions.list_for_user(recipient.id).json()) == 1


# ------------------------------- error message validation -------------------------------
@pytest.mark.validation
@pytest.mark.parametrize("amount,field,message", [
    ("", "amount", "Enter an amount greater than 0"),
    ("0", "amount", "Enter an amount greater than 0"),
    ("-5", "amount", "Enter an amount greater than 0"),
    ("abc", "amount", "Enter an amount greater than 0"),
], ids=["empty", "zero", "negative", "not-a-number"])
def test_amount_validation_messages(user, recipient, transactions_page, amount, field, message):
    transactions_page.goto(user.id)
    transactions_page.submit(amount, "transfer", recipient.id)
    expect(transactions_page.field_error(field)).to_have_text(message)
    expect(transactions_page.success).to_be_hidden()
    expect(transactions_page.rows).to_have_count(0)


@pytest.mark.validation
def test_transfer_requires_a_recipient(user, transactions_page):
    transactions_page.goto(user.id)
    transactions_page.submit(10, "transfer", "")
    expect(transactions_page.field_error("recipient")).to_have_text("Recipient ID is required for transfers")


@pytest.mark.validation
def test_unknown_recipient_shows_server_error(user, transactions_page):
    transactions_page.goto(user.id)
    transactions_page.submit(10, "transfer", unknown_id())
    expect(transactions_page.form_error).to_have_text("Recipient not found")
    expect(transactions_page.rows).to_have_count(0)


@pytest.mark.validation
def test_transferring_to_yourself_shows_server_error(user, transactions_page):
    transactions_page.goto(user.id)
    transactions_page.submit(10, "transfer", user.id)
    expect(transactions_page.form_error).to_have_text("Validation failed")


@pytest.mark.validation
def test_limit_exceeded_message_names_the_account_type(user, recipient, transactions_page):
    transactions_page.goto(user.id)                       # basic account, limit $1,000
    transactions_page.submit(1_000.01, "transfer", recipient.id)
    expect(transactions_page.form_error).to_have_text("Amount exceeds the transaction limit for basic accounts")
    expect(transactions_page.rows).to_have_count(0)


@pytest.mark.validation
def test_error_clears_after_a_successful_retry(user, recipient, transactions_page):
    transactions_page.goto(user.id)
    transactions_page.submit(5_000, "transfer", recipient.id)
    expect(transactions_page.form_error).to_be_visible()
    transactions_page.submit(50, "transfer", recipient.id)
    expect(transactions_page.form_error).to_be_hidden()
    expect(transactions_page.success).to_be_visible()


@pytest.mark.validation
def test_unknown_user_shows_page_error(transactions_page):
    transactions_page.goto(unknown_id())
    expect(transactions_page.page_error).to_have_text("User not found")
