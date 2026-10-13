"""
Responsive layout and multi-device viewport tests for FinPulse.
Validates that crucial controls (crucible state machine, country tabs, SQL terminal)
remain accessible and functional across Mobile, Tablet, and Desktop screen widths.
"""

from selenium.webdriver.support.wait import WebDriverWait
from tests_e2e.locators import FinPulseLocators
from tests_e2e.pages.finpulse_page import FinPulsePage


def test_desktop_viewport_interaction(driver, app_server):
    """Test full interaction flow on standard 1080p desktop viewport."""
    driver.set_window_size(1920, 1080)
    page = FinPulsePage(driver, app_server)
    page.open()

    page.inject_poison_packet()
    assert "poison quarantined" in page.get_crucible_badge_text()
    page.select_country("TZA")
    assert page.get_country_kpis()["rate"] == "16.67%"


def test_tablet_viewport_interaction(driver, app_server):
    """Test interaction flow on iPad / tablet portrait dimensions (768x1024)."""
    driver.set_window_size(768, 1024)
    page = FinPulsePage(driver, app_server)
    page.open()

    # Verify hero lede and crucible action on tablet
    assert len(page.get_hero_lede()) > 0
    page.inject_poison_packet()
    page.apply_schema_patch()
    page.replay_dlq_partition()
    assert "reconciled" in page.get_crucible_badge_text()


def test_mobile_viewport_interaction(driver, app_server):
    """Test interaction flow on mobile viewport (375x812 iPhone dimension)."""
    driver.set_window_size(375, 812)
    page = FinPulsePage(driver, app_server)
    page.open()

    # Country tabs and terminal buttons on mobile
    page.select_country("ZMB")
    assert page.get_country_kpis()["rate"] == "61.54%"

    page.select_preset_query("mart_credit_funnel")
    first_row = page.get_query_table_first_row()
    assert first_row == ["172", "58", "26", "19", "14"]
