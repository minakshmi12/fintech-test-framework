from playwright.sync_api import Page, expect


class RegistrationPage:
    """Page object for the user registration form."""

    def __init__(self, page: Page):
        self.page = page
        self.success = page.get_by_test_id("registration-success")
        self.form_error = page.get_by_test_id("form-error")

    def goto(self) -> None:
        """Open the registration page."""
        self.page.goto("/")

    def register(self, name: str = "", email: str = "", account_type: str | None = None) -> None:
        """Fill in and submit the form; the account type is left at its default when None."""
        self.page.get_by_test_id("name").fill(name)
        self.page.get_by_test_id("email").fill(email)
        if account_type:
            self.page.get_by_test_id("account-type").select_option(account_type)
        self.page.get_by_test_id("register-submit").click()

    def field_error(self, field: str):
        """Locator for a field's validation message."""
        return self.page.get_by_test_id(f"{field}-error")

    def created_user_id(self) -> str:
        """Wait for the success message and return the new user's id."""
        expect(self.success).to_be_visible()
        return self.page.get_by_test_id("user-id").inner_text()

    def go_to_transactions(self) -> None:
        """Follow the link to the transactions page."""
        self.page.get_by_test_id("go-to-transactions").click()
