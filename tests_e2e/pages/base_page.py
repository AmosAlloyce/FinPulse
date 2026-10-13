"""
Base Page Object providing explicit wait utilities and interaction helpers.
Strictly adheres to AGENTS.md rules:
- No fixed sleeps (sleep()).
- Only explicit WebDriverWait using Expected Conditions.
- No implicit waits.
"""

from typing import List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class BasePage:
    def __init__(self, driver: WebDriver, timeout: float = 10.0):
        self.driver = driver
        self.timeout = timeout
        self.wait = WebDriverWait(self.driver, timeout=self.timeout)

    def navigate_to(self, url: str) -> None:
        self.driver.get(url)

    def find_visible_element(self, locator: Tuple[str, str]) -> WebElement:
        """Wait until an element is visible in the DOM."""
        return self.wait.until(EC.visibility_of_element_located(locator))

    def find_present_element(self, locator: Tuple[str, str]) -> WebElement:
        """Wait until an element is present in the DOM."""
        return self.wait.until(EC.presence_of_element_located(locator))

    def find_all_elements(self, locator: Tuple[str, str]) -> List[WebElement]:
        """Wait until at least one element matching locator is present."""
        return self.wait.until(EC.presence_of_all_elements_located(locator))

    def scroll_into_view(self, element: WebElement) -> WebElement:
        """Safely bring an element into viewport center to prevent header interception."""
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element)
        return element

    def click(self, locator: Tuple[str, str]) -> None:
        """Scroll element into view, wait for clickability, and click."""
        element = self.find_present_element(locator)
        self.scroll_into_view(element)
        clickable_element = self.wait.until(EC.element_to_be_clickable(element))
        clickable_element.click()

    def get_text(self, locator: Tuple[str, str]) -> str:
        """Retrieve inner text of an element once visible."""
        return self.find_visible_element(locator).text.strip()

    def get_attribute(self, locator: Tuple[str, str], attribute: str) -> str:
        """Retrieve attribute value of an element."""
        element = self.find_present_element(locator)
        return element.get_attribute(attribute) or ""

    def wait_for_text_to_be_present(self, locator: Tuple[str, str], text: str) -> bool:
        """Wait explicitly until specific text appears in the element."""
        return bool(self.wait.until(EC.text_to_be_present_in_element(locator, text)))

    def wait_for_element_enabled(self, locator: Tuple[str, str]) -> WebElement:
        """Wait explicitly until element is enabled and not disabled."""
        return self.wait.until(lambda d: d.find_element(*locator) if d.find_element(*locator).is_enabled() else False)

    def wait_for_element_disabled(self, locator: Tuple[str, str]) -> bool:
        """Wait explicitly until element has disabled attribute or property."""
        return bool(self.wait.until(lambda d: not d.find_element(*locator).is_enabled()))
