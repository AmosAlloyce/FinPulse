"""
Tests for Act 8: Operable Warehouse SQL Terminal Simulator.
Validates preset query selection, custom SQL execution, and responsive results table rendering.
"""

from tests_e2e.locators import FinPulseLocators
from tests_e2e.pages.finpulse_page import FinPulsePage


def test_default_terminal_query_and_table(driver, app_server):
    """Verify initial SQL terminal input value and default table rows for country performance."""
    page = FinPulsePage(driver, app_server)
    page.open()

    input_val = page.get_attribute(FinPulseLocators.SQL_INPUT, "value")
    assert input_val == "SELECT * FROM mart_country_performance;"

    headers = page.get_query_table_headers()
    expected_headers = [
        "country_code", "applicants", "applications", "approvals",
        "approval_rate_pct", "approved_value_local", "avg_credit_score", "par30_pct"
    ]
    assert headers == expected_headers

    row_count = page.get_query_table_row_count()
    assert row_count == 5


def test_preset_credit_funnel_query(driver, app_server):
    """Verify selecting mart_credit_funnel preset updates input and displays 1 funnel row."""
    page = FinPulsePage(driver, app_server)
    page.open()

    page.select_preset_query("mart_credit_funnel")

    headers = page.get_query_table_headers()
    expected_headers = ["applications", "decisions", "approvals", "loans_with_repayment", "settled_payments"]
    assert headers == expected_headers

    row_count = page.get_query_table_row_count()
    assert row_count == 1

    first_row = page.get_query_table_first_row()
    assert first_row == ["172", "58", "26", "19", "14"]


def test_preset_quality_issues_query(driver, app_server):
    """Verify selecting quality_issues preset updates input and displays quarantine issue rows."""
    page = FinPulsePage(driver, app_server)
    page.open()

    page.select_preset_query("quality_issues")

    headers = page.get_query_table_headers()
    assert headers == ["rule", "severity", "message"]

    row_count = page.get_query_table_row_count()
    assert row_count == 2

    first_row = page.get_query_table_first_row()
    assert first_row[0] == "schema_contract"
    assert first_row[1] == "ERROR"
    assert "validation errors" in first_row[2]


def test_preset_customer_features_query(driver, app_server):
    """Verify selecting customer features preset updates input and displays 4 feature store rows."""
    page = FinPulsePage(driver, app_server)
    page.open()

    page.select_preset_query("mart_customer_features")

    headers = page.get_query_table_headers()
    assert headers == ["customer_id", "income_band", "avg_credit_score", "total_airtime_topup"]

    row_count = page.get_query_table_row_count()
    assert row_count == 4


def test_custom_sql_input_execution(driver, app_server):
    """Verify typing a custom SQL statement and clicking 'Run query' triggers execution."""
    page = FinPulsePage(driver, app_server)
    page.open()

    page.execute_custom_query("SELECT * FROM test_credit_funnel_view;")
    headers = page.get_query_table_headers()
    assert "decisions" in headers
    assert "settled_payments" in headers
