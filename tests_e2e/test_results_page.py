"""
Tests for the FinPulse E2E Test Suite Results presentation page (tests.html).
Validates HUD cards, filter pills, search input, and expandable step drawers.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tests_e2e.pages.base_page import BasePage


def test_results_page_hud_telemetry(driver, app_server):
    """Verify test results page loads and displays 24/24 pass rate and HUD telemetry."""
    driver.get(f"{app_server}/finpulse/tests.html")
    wait = WebDriverWait(driver, 5)

    wait.until(EC.title_contains("E2E Test Suite Results"))

    hud_cards = driver.find_elements(By.CSS_SELECTOR, ".hud-card")
    assert len(hud_cards) == 4

    hud_text = " ".join([c.text for c in hud_cards])
    assert "28 / 28" in hud_text
    assert "100% successful execution" in hud_text
    assert "0" in hud_text
    assert "BiDi Active" in hud_text


def test_results_page_filtering_and_search(driver, app_server):
    """Verify filter pills and search input dynamically filter displayed test cards."""
    driver.get(f"{app_server}/finpulse/tests.html")
    wait = WebDriverWait(driver, 5)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".test-card")))

    all_cards = driver.find_elements(By.CSS_SELECTOR, ".test-card")
    assert len(all_cards) == 28

    # Click 'Crucible' filter pill
    btn_crucible = driver.find_element(By.CSS_SELECTOR, "button[data-filter='crucible']")
    btn_crucible.click()

    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".test-card")) == 4)
    crucible_cards = driver.find_elements(By.CSS_SELECTOR, ".test-card")
    assert len(crucible_cards) == 4

    # Type search query
    search_input = driver.find_element(By.ID, "search-input")
    search_input.send_keys("test_crucible_end_to_end_replay_lifecycle")

    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".test-card")) == 1)
    matching_card = driver.find_element(By.CSS_SELECTOR, ".test-card")
    assert "test_crucible_end_to_end_replay_lifecycle" in matching_card.text


def test_results_page_expandable_test_card_drawer(driver, app_server):
    """Verify clicking a test card expands the assertion steps drawer."""
    driver.get(f"{app_server}/finpulse/tests.html")
    wait = WebDriverWait(driver, 5)

    first_card = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".test-card")))
    first_card.click()

    wait.until(lambda d: "expanded" in first_card.get_attribute("class"))
    drawer = first_card.find_element(By.CSS_SELECTOR, ".test-drawer")
    assert drawer.is_displayed()
    assert "Asserted Steps & Verification Flow" in drawer.text


def test_lakehouse_navigation_link_to_results(driver, app_server):
    """Verify the main FinPulse page links to the test results page."""
    driver.get(f"{app_server}/finpulse/index.html")
    wait = WebDriverWait(driver, 5)

    test_badge_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='tests.html']")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", test_badge_link)
    test_badge_link.click()

    wait.until(EC.title_contains("E2E Test Suite Results"))
    assert driver.current_url.endswith("/finpulse/tests.html")
