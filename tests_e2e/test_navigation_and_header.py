"""
Tests for FinPulse header ribbon, accessibility skip-link, navigation links, and Act 1 Hero HUD.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from tests_e2e.locators import FinPulseLocators
from tests_e2e.pages.finpulse_page import FinPulsePage


def test_page_title_and_metadata(driver, app_server):
    """Verify document title, description, and accessibility skip-link."""
    page = FinPulsePage(driver, app_server)
    page.open()

    assert "FinPulse" in driver.title
    assert "Real-time credit data platform" in driver.title

    meta_desc = driver.find_element(By.CSS_SELECTOR, "meta[name='description']").get_attribute("content")
    assert "Medallion Lakehouse" in meta_desc
    assert "5 African markets" in meta_desc


def test_keyboard_accessibility_skip_link(driver, app_server):
    """Verify skip-to-content link exists, points to #main-content, and is accessible."""
    page = FinPulsePage(driver, app_server)
    page.open()

    skip_link = driver.find_element(*FinPulseLocators.SKIP_LINK)
    assert skip_link.get_attribute("href").endswith("#main-content")
    # Off-screen accessible elements return textContent
    assert skip_link.get_attribute("textContent").strip() == "Skip to content"

    # Focus the skip link and verify it moves into view
    driver.execute_script("arguments[0].focus();", skip_link)
    active_elem = driver.switch_to.active_element
    assert active_elem == skip_link


def test_telemetry_ribbon_brand_and_stats(driver, app_server):
    """Verify navigation ribbon branding, pulsing indicator, live event stats, and E2E test badge."""
    page = FinPulsePage(driver, app_server)
    page.open()

    brand = page.get_brand_name()
    assert brand == "FinPulse"

    stat_text = page.get_text(FinPulseLocators.RIBBON_EVENT_STAT)
    assert "2,010 events" in stat_text
    assert "5 markets" in stat_text

    badge_text = page.get_text(FinPulseLocators.RIBBON_TEST_BADGE)
    assert "28/28 E2E Pass" in badge_text


def test_navigation_jump_links_structure(driver, app_server):
    """Verify all 8 narrative act links exist in sequence with correct anchors."""
    page = FinPulsePage(driver, app_server)
    page.open()

    items = page.get_navigation_items()
    expected_acts = [
        ("01 Ingress", "#act-ingress"),
        ("02 Spark stream", "#act-spark"),
        ("03 DLQ crucible", "#act-crucible"),
        ("04 Lakehouse", "#act-lakehouse"),
        ("05 dbt marts", "#act-dbt"),
        ("06 Market risk", "#act-radar"),
        ("07 Production SRE", "#act-observability"),
        ("08 SQL terminal", "#act-console"),
    ]

    assert len(items) == len(expected_acts)
    for (actual_text, actual_href), (expected_text, expected_anchor) in zip(items, expected_acts):
        assert actual_text == expected_text
        assert actual_href.endswith(expected_anchor)


def test_hero_hud_metrics(driver, app_server):
    """Verify HUD cards in Act 1 display accurate baseline telemetry."""
    page = FinPulsePage(driver, app_server)
    page.open()

    hud_data = page.get_hud_stats_data()
    assert len(hud_data) == 4

    labels = [item["label"].upper() for item in hud_data]
    assert "INGESTED EVENTS" in labels
    assert "ACCEPTANCE RATE" in labels
    assert "P95 INGRESS LAG" in labels
    assert "QUARANTINED RECORDS" in labels

    values = {item["label"].upper(): item["value"] for item in hud_data}
    assert values["INGESTED EVENTS"] == "2,010"
    assert values["ACCEPTANCE RATE"] == "99.90%"
    assert values["P95 INGRESS LAG"] == "420 ms"
    assert values["QUARANTINED RECORDS"] == "2 DLQ"


def test_repository_external_links_security(driver, app_server):
    """Verify all repository links specify noopener noreferrer and blank target."""
    page = FinPulsePage(driver, app_server)
    page.open()

    repo_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='github.com/AmosAlloyce/FinPulse']")
    assert len(repo_links) >= 2

    for link in repo_links:
        assert link.get_attribute("target") == "_blank"
        rel_attr = link.get_attribute("rel") or ""
        assert "noopener" in rel_attr
        assert "noreferrer" in rel_attr
