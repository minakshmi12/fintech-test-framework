"""
Reporting plugin.

Per run, in reports/:
  report.html     pytest-html (self-contained; failures embed the screenshot + API call log)
  junit.xml       pytest built-in, for CI dashboards
  results.json    machine-readable results (per test: outcome, duration, error, screenshot)
  summary.md      human-readable summary (totals, per-area breakdown, slowest tests, failures)
  screenshots/    PNG per failed UI test
  api_logs/       JSON-lines log of every API call (one file per xdist worker)
  artifacts/      Playwright videos + traces for failed UI tests
"""
from __future__ import annotations

import base64
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPORTS = Path("reports")
_results: list[dict] = []
_reruns = 0
_started = 0.0


def _slug(nodeid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid)[:150]


def _area(nodeid: str) -> str:
    return "ui" if nodeid.replace("\\", "/").startswith("tests/ui") else "api"


# --------------------------- failure artifacts (screenshot + API log) ---------------------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    failed_now = call.excinfo is not None and call.when in ("setup", "call")
    screenshot_png: bytes | None = None
    api_text: str | None = None

    if failed_now:
        page = item.funcargs.get("page")
        if page is not None:
            try:
                if not page.is_closed():
                    screenshot_png = page.screenshot(full_page=True)
                    path = REPORTS / "screenshots" / f"{_slug(item.nodeid)}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(screenshot_png)
                    item.user_properties.append(("screenshot", str(path)))
            except Exception:  # noqa: BLE001 - never let artifact capture hide the real failure
                pass
        logger = getattr(item, "api_log", None)
        if logger is not None and logger.entries:
            api_text = logger.as_text()

    outcome = yield
    report = outcome.get_result()

    if screenshot_png or api_text:
        try:
            from pytest_html import extras
        except ImportError:
            return
        report_extras = getattr(report, "extras", [])
        if screenshot_png:
            report_extras.append(extras.png(base64.b64encode(screenshot_png).decode(), "Screenshot at failure"))
        if api_text:
            report_extras.append(extras.text(api_text, "API calls"))
        report.extras = report_extras


# --------------------------------------- result collection ---------------------------------------
def pytest_sessionstart(session):
    global _started
    _started = time.time()


def pytest_runtest_logreport(report):
    global _reruns
    if report.outcome == "rerun":
        _reruns += 1
        return
    if report.when == "call" or (report.when in ("setup", "teardown") and report.outcome != "passed"):
        if report.when == "teardown" and any(r["nodeid"] == report.nodeid for r in _results):
            return
        props = dict(report.user_properties)
        _results.append({
            "nodeid": report.nodeid,
            "area": _area(report.nodeid),
            "outcome": report.outcome,
            "duration_s": round(report.duration, 3),
            "error": (report.longreprtext.strip().splitlines() or [""])[-1] if report.failed else None,
            "screenshot": props.get("screenshot"),
        })


def pytest_sessionfinish(session, exitstatus):
    if hasattr(session.config, "workerinput"):  # xdist worker: the controller writes the reports
        return
    from config.settings import get_config
    from fintech_test_automation.data.factories import RUN_ID

    env = get_config().name
    count = lambda o: sum(1 for r in _results if r["outcome"] == o)  # noqa: E731
    totals = {"passed": count("passed"), "failed": count("failed"), "skipped": count("skipped"), "reruns": _reruns}
    duration = round(time.time() - _started, 2)

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "results.json").write_text(json.dumps({
        "run": {"environment": env, "run_id": RUN_ID, "finished": datetime.now(timezone.utc).isoformat(),
                "duration_s": duration, "totals": totals},
        "tests": sorted(_results, key=lambda r: r["nodeid"]),
    }, indent=2))

    by_area: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in _results:
        by_area[r["area"]][r["outcome"]] += 1
    slowest = sorted((r for r in _results if r["outcome"] == "passed"), key=lambda r: r["duration_s"], reverse=True)[:5]
    failures = [r for r in _results if r["outcome"] == "failed"]

    lines = [
        "# Test run summary", "",
        f"- **Environment:** {env}   |   **Run ID:** {RUN_ID}   |   **Duration:** {duration}s",
        f"- **Passed:** {totals['passed']}  |  **Failed:** {totals['failed']}  |  "
        f"**Skipped:** {totals['skipped']}  |  **Reruns:** {totals['reruns']}",
        "", "| Area | Passed | Failed | Skipped |", "|---|---|---|---|",
        *[f"| {a} | {c['passed']} | {c['failed']} | {c['skipped']} |" for a, c in sorted(by_area.items())],
        "", "## Slowest tests", *[f"- {r['duration_s']:.2f}s — {r['nodeid']}" for r in slowest],
    ]
    if failures:
        lines += ["", "## Failures"]
        for r in failures:
            lines.append(f"- **{r['nodeid']}**\n  - {r['error']}")
            if r["screenshot"]:
                lines.append(f"  - screenshot: `{r['screenshot']}`")
    (REPORTS / "summary.md").write_text("\n".join(lines) + "\n")


def pytest_html_report_title(report):
    report.title = "Fintech Platform – Test Report"
