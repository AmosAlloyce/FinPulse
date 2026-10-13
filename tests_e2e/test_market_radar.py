"""
Tests for Act 6: Multi-Market Credit Risk & Growth Radar.
Validates tab switching, ARIA accessibility attributes, and dynamic KPI calculations across all 5 African markets.
"""

from tests_e2e.locators import FinPulseLocators
from tests_e2e.pages.finpulse_page import FinPulsePage


EXPECTED_MARKET_DATA = {
    "KEN": {
        "rate": "41.18%",
        "score": "572.5",
        "par30": "20.00%",
        "volume": "1,957.20",
        "currency": "KES",
        "desc_snippet": "Kenya: 56 applications evaluated",
    },
    "UGA": {
        "rate": "28.57%",
        "score": "504.0",
        "par30": "25.00%",
        "volume": "26,070.00",
        "currency": "UGX",
        "desc_snippet": "Uganda: 36 applications across 15 applicants",
    },
    "GHA": {
        "rate": "75.00%",
        "score": "652.9",
        "par30": "50.00%",
        "volume": "140.31",
        "currency": "GHS",
        "desc_snippet": "Ghana: 29 applications across 17 applicants",
    },
    "TZA": {
        "rate": "16.67%",
        "score": "488.3",
        "par30": "0.00%",
        "volume": "4,479.50",
        "currency": "TZS",
        "desc_snippet": "Tanzania: 16 applications across 8 applicants",
    },
    "ZMB": {
        "rate": "61.54%",
        "score": "593.4",
        "par30": "0.00%",
        "volume": "324.56",
        "currency": "ZMW",
        "desc_snippet": "Zambia: 35 applications across 13 applicants",
    },
}


def test_default_active_country_kenya(driver, app_server):
    """Verify Kenya (KEN) is selected by default with corresponding KPIs."""
    page = FinPulsePage(driver, app_server)
    page.open()

    assert page.get_active_country_code() == "KEN"
    kpis = page.get_country_kpis()

    assert kpis["rate"] == EXPECTED_MARKET_DATA["KEN"]["rate"]
    assert kpis["score"] == EXPECTED_MARKET_DATA["KEN"]["score"]
    assert kpis["par30"] == EXPECTED_MARKET_DATA["KEN"]["par30"]
    assert kpis["volume"] == EXPECTED_MARKET_DATA["KEN"]["volume"]
    assert EXPECTED_MARKET_DATA["KEN"]["currency"] in kpis["volume_lbl"]
    assert EXPECTED_MARKET_DATA["KEN"]["desc_snippet"] in kpis["detail"]


def test_country_switcher_all_african_markets(driver, app_server):
    """Verify switching between all 5 countries correctly updates metrics and currencies."""
    page = FinPulsePage(driver, app_server)
    page.open()

    for code, expected in EXPECTED_MARKET_DATA.items():
        page.select_country(code)
        assert page.get_active_country_code() == code

        kpis = page.get_country_kpis()
        assert kpis["rate"] == expected["rate"]
        assert kpis["score"] == expected["score"]
        assert kpis["par30"] == expected["par30"]
        assert kpis["volume"] == expected["volume"]
        assert expected["currency"] in kpis["volume_lbl"]
        assert expected["desc_snippet"] in kpis["detail"]


def test_country_selector_aria_selected_state(driver, app_server):
    """Verify WAI-ARIA tablist accessibility attributes on country buttons."""
    page = FinPulsePage(driver, app_server)
    page.open()

    buttons = driver.find_elements(*FinPulseLocators.COUNTRY_BUTTONS)
    assert len(buttons) == 5

    # Select Ghana
    page.select_country("GHA")

    for btn in buttons:
        country = btn.get_attribute("data-country")
        aria_selected = btn.get_attribute("aria-selected")
        if country == "GHA":
            assert aria_selected == "true"
            assert "active" in btn.get_attribute("class")
        else:
            assert aria_selected == "false"
            assert "active" not in btn.get_attribute("class")
