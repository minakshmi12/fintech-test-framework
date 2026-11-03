# Fintech Test Automation Framework (Playwright + Python)

pytest + Playwright (sync API) for a microservices fintech platform (User, Transaction and Notification
services behind an API gateway). API tests use Playwright's `APIRequestContext`; UI tests use a real browser.

```bash
pip install -r requirements.txt && playwright install chromium

pytest -n 4                  # everything, in parallel, against the built-in mock platform
pytest -m smoke              # fast subset            (also: -m api | ui | regression | auth | validation)
pytest tests/api             # API only (no browser launched)
pytest --env=staging         # or TEST_ENV=staging  (see "Environments")
pytest --headed --slowmo 300 tests/ui
```

## API under test
| Endpoint | Notes |
|---|---|
| `POST /api/users` `{name, email, accountType}` | `accountType`: basic (default) / premium / business |
| `GET /api/users/:id` | |
| `POST /api/transactions` `{userId, amount, type, recipientId}` | `type`: transfer / deposit / withdrawal; per-account-type limits |
| `GET /api/transactions/:userId` | sent **and** received, newest first |

Added beyond the brief (needed for full CRUD and for test-data clean-up): `PUT /api/users/:id`,
`DELETE /api/users/:id`, and `GET /api/notifications/:userId` (async cross-service check).
Because the brief doesn't define auth, the mock uses `Authorization: Bearer <token>` with a full-access token and a
read-only token. Swap in your real scheme in `fintech_test_automation/clients/base.py` and `config/settings.py`.
Error envelope assumed: `{"error": {"code", "message", "details": [{"field", "message"}]}}`.

## What's covered
| Area | Files |
|---|---|
| CRUD | `tests/api/test_users_crud.py`, `test_transactions.py` |
| Error scenarios | 404s, 409 duplicate, 422 limit exceeded, malformed JSON (`test_users_validation.py`, `test_transactions.py`) |
| Data validation | data-driven from catalogues in `fintech_test_automation/data/factories.py` (types, boundaries, decimals, enums, field-level details) |
| AuthN / AuthZ | `tests/api/test_auth.py`: no/invalid/malformed credentials → 401 on every endpoint, read-only token → 403 on writes with no side effects |
| Cross-service | `test_cross_service.py`: transfer → async notification (polling, no `sleep`) |
| UI | `tests/ui/test_registration.py`, `test_transactions.py`: registration, transaction creation, field + server error messages, end-to-end journey; UI results are cross-checked against the API |

## Test utilities (`fintech_test_automation/`)
- `data/factories.py`: `build_user`, `build_transaction`, `build_amount`, invalid-payload catalogues. Unique, run-id-tagged data.
- `data/manager.py`: `TestDataManager` creates data via the API, tracks it, deletes it in teardown (also `track()` for users created through the UI).
- `assertions.py`: `assert_status`, `assert_error`, `assert_user`, `assert_transaction`, `assert_amount` (Decimal), `assert_newest_first`, `assert_iso_timestamp`. Failures print the request and response.
- `utils/helpers.py`, `utils/polling.py`: `money`, `find_by_id`, `eventually`.
- `clients/`: one client per service; `.with_token(t)` / `.anonymous()` for auth tests.
- `pages/`: page objects (`data-testid` locators).

## Environments (`config/settings.py`)
`local` (starts the mock platform automatically), `qa`, `staging`: URLs, timeouts, flaky-test reruns.
Overrides: `BASE_URL`, `API_URL`, `API_TOKEN`, `READONLY_TOKEN` (env vars or `.env`, see `.env.example`).
Tests needing the read-only token skip if it isn't configured.

## Reports (`reports/`)
| File | Purpose |
|---|---|
| `report.html` | pytest-html, self-contained. **Failures embed a full-page screenshot and the API call log.** |
| `junit.xml` | CI dashboards |
| `results.json` | machine-readable: per-test outcome, duration, error, screenshot path |
| `summary.md` | totals, per-area breakdown, slowest tests, failures |
| `screenshots/` | PNG per failed UI test |
| `api_logs/*.jsonl` | every API call: method, URL, status, duration, bodies; `Authorization` redacted |
| `artifacts/` | Playwright video + trace for failed UI tests (`playwright show-trace trace.zip`) |
