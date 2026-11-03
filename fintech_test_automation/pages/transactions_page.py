from playwright.sync_api import Page


class TransactionsPage:
    """Page object for creating transactions and viewing a user's history."""

    def __init__(self, page: Page):
        self.page = page
        self.success = page.get_by_test_id("transaction-success")
        self.form_error = page.get_by_test_id("form-error")
        self.page_error = page.get_by_test_id("page-error")
        self.summary = page.get_by_test_id("account-summary")
        self.recipient_group = page.get_by_test_id("recipient-group")
        self.rows = page.get_by_test_id("history-row")
        self.empty = page.get_by_test_id("history-empty")

    def goto(self, user_id: str) -> None:
        """Open the transactions page for a user."""
        self.page.goto(f"/transactions.html?userId={user_id}")

    def submit(self, amount: float | str = "", tx_type: str = "transfer", recipient_id: str = "") -> None:
        """Fill in and submit the transaction form."""
        self.page.get_by_test_id("type").select_option(tx_type)
        self.page.get_by_test_id("amount").fill(str(amount))
        if tx_type == "transfer":
            self.page.get_by_test_id("recipient-id").fill(recipient_id)
        self.page.get_by_test_id("tx-submit").click()

    def field_error(self, field: str):
        """Locator for a field's validation message."""
        return self.page.get_by_test_id(f"{field}-error")
