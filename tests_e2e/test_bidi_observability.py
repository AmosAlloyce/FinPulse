"""
Tests for browser events and network monitoring via WebDriver BiDi.
Strictly adheres to AGENTS.md:
- Uses WebDriver BiDi for console logs, JavaScript errors, and network interception.
- Avoids deprecated Chrome DevTools Protocol (CDP).
"""

from selenium.webdriver.support.wait import WebDriverWait
from tests_e2e.pages.finpulse_page import FinPulsePage


def test_bidi_zero_uncaught_javascript_errors_during_interactions(driver, app_server):
    """Verify using BiDi error handler that zero unhandled JavaScript exceptions occur during page usage."""
    captured_errors = []
    driver.script.add_javascript_error_handler(captured_errors.append)

    page = FinPulsePage(driver, app_server)
    page.open()

    # Perform interactive actions across multiple acts
    page.inject_poison_packet()
    page.apply_schema_patch()
    page.replay_dlq_partition()
    page.reset_crucible()
    page.select_country("GHA")
    page.select_country("ZMB")
    page.select_preset_query("mart_credit_funnel")

    # Assert that no uncaught exceptions were triggered during any of these flows
    assert len(captured_errors) == 0, f"Uncaught JS exceptions detected via BiDi: {captured_errors}"


def test_bidi_console_log_interception(driver, app_server):
    """Verify WebDriver BiDi captures real-time browser console messages."""
    console_entries = []
    driver.script.add_console_message_handler(console_entries.append)

    page = FinPulsePage(driver, app_server)
    page.open()

    # Emit a monitored log via browser evaluation
    driver.execute_script("console.log('FinPulse BiDi Telemetry Probe Online');")

    # Wait explicitly for BiDi event dispatch
    WebDriverWait(driver, 5).until(
        lambda _: any("FinPulse BiDi Telemetry Probe Online" in getattr(entry, "text", "") for entry in console_entries)
    )

    matching_entry = next(e for e in console_entries if "FinPulse BiDi Telemetry Probe Online" in getattr(e, "text", ""))
    assert matching_entry is not None


def test_bidi_network_interception(driver, app_server):
    """Verify WebDriver BiDi network interception operates cleanly without CDP."""
    intercept = driver.network._add_intercept()
    assert intercept is not None
    assert "intercept" in intercept

    # Verify and cleanly remove intercept
    driver.network._remove_intercept(intercept["intercept"])
    assert driver.network.intercepts == []
