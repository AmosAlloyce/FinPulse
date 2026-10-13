## Browser automation

This project uses Selenium 4.49.0.

### Docs
- Index: https://www.selenium.dev/llms.txt
- Reference: https://www.selenium.dev/documentation/
- Examples: https://github.com/SeleniumHQ/seleniumhq.github.io/tree/trunk/examples
- Fetch the relevant page before using an API you are not certain about.
- Do not use the legacy or CDP pages as a basis for new code.
- Do not use APIs from Selenium 3 or earlier. If an API is not in the
  current documentation or API reference, it does not exist.

### Drivers and browsers
- Selenium Manager downloads and caches the drivers. Do not add a
  driver-manager dependency, do not download drivers, and do not set
  a path to a driver binary.
- Browser configuration goes in that browser's Options class. Do not
  use DesiredCapabilities and do not pass raw capability maps.
- Headless is a browser argument: `--headless=new`.

### Waiting
- Never sleep in a test.
- Use an explicit wait, and wait for the condition the next line
  actually depends on.
- Do not set an implicit wait and also use explicit waits in the
  same session.
- When a test is flaky, find the condition that was not yet true.
  Do not increase a timeout.

### Locators
- Prefer `id` and `name`, then a CSS selector on a stable attribute
  such as `data-test`.
- Do not write absolute XPath and do not use generated class names.
- Declare locators separately from the code that finds the element.

### Sessions
- One fresh session per test. Always quit the driver in teardown -
  `quit`, not `close`.
- Do not share a driver between tests or hold one in a global.

### Events and network
- Use WebDriver BiDi for console logs, JavaScript errors, and network
  interception. Do not use the Chrome DevTools Protocol.

### Running tests
- All tests: `finpulse-repo/.venv/bin/pytest tests_e2e/ -v`
- A single test: `finpulse-repo/.venv/bin/pytest tests_e2e/test_crucible_state_machine.py -v`
- If you are unsure whether a locator or a flow works, write a
  throwaway script and run it against the application instead of
  guessing.
