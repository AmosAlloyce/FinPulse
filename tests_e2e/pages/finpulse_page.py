"""
Page Object model for FinPulse Lakehouse showcase website.
Encapsulates all user flows and state transitions across the 8 narrative acts.
"""

from typing import Dict, List, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC

from tests_e2e.locators import FinPulseLocators
from tests_e2e.pages.base_page import BasePage


class FinPulsePage(BasePage):
    def __init__(self, driver: WebDriver, base_url: str):
        super().__init__(driver)
        self.url = f"{base_url.rstrip('/')}/finpulse/index.html"

    def open(self) -> None:
        """Open the FinPulse page and wait for document completion and title."""
        self.navigate_to(self.url)
        self.wait.until(EC.title_contains("FinPulse"))
        self.find_visible_element(FinPulseLocators.HERO_TITLE)

    # Act 1 & Navigation
    def get_brand_name(self) -> str:
        return self.get_text(FinPulseLocators.BRAND_TEXT)

    def get_navigation_items(self) -> List[Tuple[str, str]]:
        """Return list of (text, href) for navigation links."""
        links = self.find_all_elements(FinPulseLocators.NAV_LINKS)
        return [(l.text.strip(), l.get_attribute("href") or "") for l in links]

    def click_nav_item(self, target_href: str) -> None:
        locator = (By.CSS_SELECTOR, f".fp-nav-links a[href='{target_href}']")
        self.click(locator)

    def get_hero_title(self) -> str:
        return self.get_text(FinPulseLocators.HERO_TITLE)

    def get_hero_lede(self) -> str:
        return self.get_text(FinPulseLocators.HERO_LEDE)

    def get_hud_stats_data(self) -> List[Dict[str, str]]:
        boxes = self.find_all_elements(FinPulseLocators.HUD_BOXES)
        results = []
        for box in boxes:
            val = box.find_element(By.CSS_SELECTOR, ".hud-val").text.strip()
            lbl = box.find_element(By.CSS_SELECTOR, ".hud-lbl").text.strip()
            results.append({"value": val, "label": lbl})
        return results

    # Act 3: DLQ Crucible State Machine
    def get_crucible_badge_text(self) -> str:
        return self.get_text(FinPulseLocators.CRUCIBLE_BADGE)

    def get_crucible_console_text(self) -> str:
        return self.get_text(FinPulseLocators.CRUCIBLE_CONSOLE)

    def is_inject_button_enabled(self) -> bool:
        elem = self.find_present_element(FinPulseLocators.BTN_INJECT_POISON)
        return elem.is_enabled()

    def is_patch_button_enabled(self) -> bool:
        elem = self.find_present_element(FinPulseLocators.BTN_PATCH_SCHEMA)
        return elem.is_enabled()

    def is_replay_button_enabled(self) -> bool:
        elem = self.find_present_element(FinPulseLocators.BTN_REPLAY_DLQ)
        return elem.is_enabled()

    def inject_poison_packet(self) -> None:
        """Click 'Inject poison packet' and wait for state transition."""
        self.click(FinPulseLocators.BTN_INJECT_POISON)
        self.wait_for_text_to_be_present(FinPulseLocators.CRUCIBLE_BADGE, "poison quarantined")
        self.wait_for_element_enabled(FinPulseLocators.BTN_PATCH_SCHEMA)
        self.wait_for_element_disabled(FinPulseLocators.BTN_INJECT_POISON)

    def apply_schema_patch(self) -> None:
        """Click 'Apply schema v1.0 patch' and wait for DLQ ready state."""
        self.click(FinPulseLocators.BTN_PATCH_SCHEMA)
        self.wait.until(lambda d: "Patch applied:" in d.find_element(*FinPulseLocators.CRUCIBLE_CONSOLE).text)
        self.wait_for_element_enabled(FinPulseLocators.BTN_REPLAY_DLQ)
        self.wait_for_element_disabled(FinPulseLocators.BTN_PATCH_SCHEMA)

    def replay_dlq_partition(self) -> None:
        """Click 'Replay DLQ partition to Silver' and wait for reconciliation."""
        self.click(FinPulseLocators.BTN_REPLAY_DLQ)
        self.wait_for_text_to_be_present(FinPulseLocators.CRUCIBLE_BADGE, "reconciled")
        self.wait_for_element_disabled(FinPulseLocators.BTN_REPLAY_DLQ)

    def reset_crucible(self) -> None:
        """Click 'Reset crucible' and wait for normal streaming state."""
        self.click(FinPulseLocators.BTN_RESET_CRUCIBLE)
        self.wait_for_text_to_be_present(FinPulseLocators.CRUCIBLE_BADGE, "normal streaming")
        self.wait_for_element_enabled(FinPulseLocators.BTN_INJECT_POISON)
        self.wait_for_element_disabled(FinPulseLocators.BTN_PATCH_SCHEMA)
        self.wait_for_element_disabled(FinPulseLocators.BTN_REPLAY_DLQ)

    def get_node_classes(self, locator: Tuple[str, str]) -> str:
        return self.get_attribute(locator, "class")

    # Act 6: Market Radar
    def select_country(self, country_code: str) -> None:
        """Click country tab (KEN, UGA, GHA, TZA, ZMB) and wait for active state."""
        locator = (By.CSS_SELECTOR, f".btn-country[data-country='{country_code}']")
        self.click(locator)
        self.wait.until(lambda d: "active" in d.find_element(*locator).get_attribute("class"))

    def get_active_country_code(self) -> str:
        active_btn = self.find_present_element((By.CSS_SELECTOR, ".btn-country.active"))
        return active_btn.get_attribute("data-country") or ""

    def get_country_kpis(self) -> Dict[str, str]:
        return {
            "rate": self.get_text(FinPulseLocators.STAT_APP_RATE),
            "score": self.get_text(FinPulseLocators.STAT_AVG_SCORE),
            "par30": self.get_text(FinPulseLocators.STAT_PAR30),
            "volume": self.get_text(FinPulseLocators.STAT_VOLUME),
            "volume_lbl": self.get_text(FinPulseLocators.STAT_VOLUME_LBL),
            "detail": self.get_text(FinPulseLocators.STAT_DETAIL),
        }

    # Act 8: SQL Terminal
    def select_preset_query(self, query_keyword: str) -> None:
        """Click preset query button containing keyword and wait for input update."""
        locator = (By.CSS_SELECTOR, f".terminal-body button[data-query*='{query_keyword}']")
        btn = self.find_present_element(locator)
        expected_query = btn.get_attribute("data-query")
        self.click(locator)
        self.wait.until(lambda d: d.find_element(*FinPulseLocators.SQL_INPUT).get_attribute("value") == expected_query)

    def execute_custom_query(self, query_sql: str) -> None:
        input_elem = self.find_present_element(FinPulseLocators.SQL_INPUT)
        self.scroll_into_view(input_elem)
        input_elem.clear()
        input_elem.send_keys(query_sql)
        self.click(FinPulseLocators.BTN_RUN_SQL)
        # Wait for table to be present and rendered
        self.find_visible_element(FinPulseLocators.RESULTS_TABLE)

    def get_query_table_headers(self) -> List[str]:
        headers = self.find_all_elements(FinPulseLocators.RESULTS_TABLE_HEADERS)
        return [h.text.strip() for h in headers]

    def get_query_table_row_count(self) -> int:
        rows = self.find_all_elements(FinPulseLocators.RESULTS_TABLE_ROWS)
        return len(rows)

    def get_query_table_first_row(self) -> List[str]:
        rows = self.find_all_elements(FinPulseLocators.RESULTS_TABLE_ROWS)
        if not rows:
            return []
        cols = rows[0].find_elements(By.CSS_SELECTOR, "td")
        return [c.text.strip() for c in cols]
