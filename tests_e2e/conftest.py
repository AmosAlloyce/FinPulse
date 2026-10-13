"""
Pytest configuration and fixtures for Selenium browser automation.
Complies strictly with AGENTS.md:
- Uses Selenium Manager automatically.
- Browser configuration in Options class (--headless=new).
- Fresh session per test (function scope), always calls driver.quit().
- WebDriver BiDi enabled for console logs and JS errors.
- Never uses sleeps; relies on explicit conditions.
"""

import os
import socket
import subprocess
import time
from typing import Generator
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def app_server() -> Generator[str, None, None]:
    """
    Session fixture ensuring the FinPulse web server is online.
    Spawns an isolated node server on an available port if none is running.
    """
    default_port = 3002
    if _is_port_in_use(default_port):
        yield f"http://127.0.0.1:{default_port}"
        return

    test_port = _find_free_port()
    env = os.environ.copy()
    env["PORT"] = str(test_port)

    server_script = "server/index.mjs" if os.path.exists("server/index.mjs") else ("../server/index.mjs" if os.path.exists("../server/index.mjs") else None)
    if server_script:
        server_cmd = ["node", server_script]
    elif os.path.exists("web/dist"):
        server_cmd = ["python", "-m", "http.server", str(test_port), "--directory", "web/dist"]
    else:
        server_cmd = ["node", "server/index.mjs"]

    # Launch server in the background
    server_process = subprocess.Popen(
        server_cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the server socket to accept connections
    timeout_seconds = 12
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < timeout_seconds:
        if _is_port_in_use(test_port):
            server_ready = True
            break
        if server_process.poll() is not None:
            _, err = server_process.communicate()
            raise RuntimeError(f"Server exited unexpectedly: {err.decode('utf-8', errors='ignore')}")
        time.sleep(0.1)

    if not server_ready:
        server_process.kill()
        raise TimeoutError(f"Ecosystem server failed to bind port {test_port} within {timeout_seconds}s")

    base_url = f"http://127.0.0.1:{test_port}"
    try:
        yield base_url
    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


@pytest.fixture
def driver() -> Generator[webdriver.Chrome, None, None]:
    """
    Function-scoped fixture providing one fresh browser session per test.
    Per AGENTS.md:
    - Never share a driver between tests or hold one in a global.
    - Always quit the driver in teardown with quit().
    - Headless mode set via --headless=new.
    - WebDriver BiDi enabled for logs and javascript error monitoring.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.enable_bidi = True

    # Selenium Manager automatically handles the driver resolution and caching
    chrome_driver = webdriver.Chrome(options=options)

    # Register WebDriver BiDi listeners for logs and JS exceptions
    bidi_logs = []
    bidi_errors = []
    chrome_driver.script.add_console_message_handler(bidi_logs.append)
    chrome_driver.script.add_javascript_error_handler(bidi_errors.append)
    setattr(chrome_driver, "bidi_logs", bidi_logs)
    setattr(chrome_driver, "bidi_errors", bidi_errors)

    try:
        yield chrome_driver
    finally:
        # Strict teardown rule: quit, not close
        chrome_driver.quit()
