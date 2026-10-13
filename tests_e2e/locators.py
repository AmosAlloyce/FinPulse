"""
Locators for the FinPulse application test suite.
In compliance with AGENTS.md:
- Locators are declared separately from the code that finds the element.
- Locators prefer `id` and `name`, then stable CSS selectors on attributes.
- No absolute XPath or generated class names.
"""

from selenium.webdriver.common.by import By


class FinPulseLocators:
    # Accessibility and Navigation Ribbon
    SKIP_LINK = (By.CSS_SELECTOR, ".skip-to-content")
    MAIN_CONTENT = (By.ID, "main-content")
    BRAND = (By.CSS_SELECTOR, ".fp-brand")
    BRAND_TEXT = (By.CSS_SELECTOR, ".fp-brand span")
    NAV_LINKS = (By.CSS_SELECTOR, ".fp-nav-links a")
    NAV_LINK_INGRESS = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-ingress']")
    NAV_LINK_SPARK = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-spark']")
    NAV_LINK_CRUCIBLE = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-crucible']")
    NAV_LINK_LAKEHOUSE = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-lakehouse']")
    NAV_LINK_DBT = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-dbt']")
    NAV_LINK_RADAR = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-radar']")
    NAV_LINK_OBSERVABILITY = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-observability']")
    NAV_LINK_CONSOLE = (By.CSS_SELECTOR, ".fp-nav-links a[href='#act-console']")
    RIBBON_EVENT_STAT = (By.CSS_SELECTOR, ".fp-ribbon-right span.fp-tag-stat")
    RIBBON_TEST_BADGE = (By.CSS_SELECTOR, ".fp-ribbon-right a.fp-tag-stat")
    RIBBON_STAT = (By.CSS_SELECTOR, ".fp-ribbon-right span.fp-tag-stat")
    HEADER_REPO_LINK = (By.CSS_SELECTOR, ".fp-ribbon-right .btn-repo")

    # Act 1: Ingress Hero Section
    HERO_SECTION = (By.ID, "act-ingress")
    HERO_TITLE = (By.CSS_SELECTOR, ".hero-display-title")
    HERO_LEDE = (By.CSS_SELECTOR, ".hero-lede")
    HERO_TEST_CRUCIBLE_CTA = (By.CSS_SELECTOR, ".hero-cta-group a[href='#act-crucible']")
    HERO_REPO_CTA = (By.CSS_SELECTOR, ".hero-cta-group a[href*='github.com']")
    HUD_BOXES = (By.CSS_SELECTOR, ".hero-hud-grid .hud-box")
    HUD_INGESTED_VAL = (By.CSS_SELECTOR, "[data-sc-count='0 2010']")

    # Act 2: Spark Engine Section
    SPARK_SECTION = (By.ID, "act-spark")
    SPARK_CODE_BLOCK = (By.CSS_SELECTOR, "#act-spark pre.fp-mono-code")

    # Act 3: DLQ Poison Packet Crucible State Machine
    CRUCIBLE_SECTION = (By.ID, "act-crucible")
    CRUCIBLE_BADGE = (By.ID, "crucible-badge")
    BTN_INJECT_POISON = (By.ID, "btn-inject-poison")
    BTN_PATCH_SCHEMA = (By.ID, "btn-patch-schema")
    BTN_REPLAY_DLQ = (By.ID, "btn-replay-dlq")
    BTN_RESET_CRUCIBLE = (By.ID, "btn-reset-crucible")
    CRUCIBLE_CONSOLE = (By.ID, "crucible-console")

    NODE_INGRESS = (By.ID, "node-ingress")
    NODE_VALIDATOR = (By.ID, "node-validator")
    NODE_QUARANTINE = (By.ID, "node-quarantine")
    NODE_SILVER = (By.ID, "node-silver")
    NODE_GOLD = (By.ID, "node-gold")

    # Act 4: Medallion Lakehouse Section
    LAKEHOUSE_SECTION = (By.ID, "act-lakehouse")
    MEDALLION_CARDS = (By.CSS_SELECTOR, ".medallion-card")

    # Act 5: dbt Marts Section
    DBT_SECTION = (By.ID, "act-dbt")
    DBT_SVG_LINEAGE = (By.CSS_SELECTOR, "#act-dbt svg[aria-label='dbt lineage diagram']")

    # Act 6: Market Performance Radar (Country Switcher)
    RADAR_SECTION = (By.ID, "act-radar")
    COUNTRY_BUTTONS = (By.CSS_SELECTOR, ".btn-country")
    COUNTRY_BTN_KEN = (By.CSS_SELECTOR, ".btn-country[data-country='KEN']")
    COUNTRY_BTN_UGA = (By.CSS_SELECTOR, ".btn-country[data-country='UGA']")
    COUNTRY_BTN_GHA = (By.CSS_SELECTOR, ".btn-country[data-country='GHA']")
    COUNTRY_BTN_TZA = (By.CSS_SELECTOR, ".btn-country[data-country='TZA']")
    COUNTRY_BTN_ZMB = (By.CSS_SELECTOR, ".btn-country[data-country='ZMB']")

    STAT_APP_RATE = (By.ID, "c-app-rate")
    STAT_AVG_SCORE = (By.ID, "c-avg-score")
    STAT_PAR30 = (By.ID, "c-par30")
    STAT_VOLUME = (By.ID, "c-volume")
    STAT_VOLUME_LBL = (By.ID, "c-volume-lbl")
    STAT_DETAIL = (By.ID, "c-detail")

    # Act 7: Observability & SRE
    OBSERVABILITY_SECTION = (By.ID, "act-observability")

    # Act 8: Operable Warehouse SQL Terminal
    CONSOLE_SECTION = (By.ID, "act-console")
    SQL_INPUT = (By.ID, "sql-input")
    BTN_RUN_SQL = (By.ID, "btn-run-sql")
    QUERY_RESULT_CONTAINER = (By.ID, "query-result-container")
    RESULTS_TABLE = (By.CSS_SELECTOR, ".terminal-results-table")
    RESULTS_TABLE_HEADERS = (By.CSS_SELECTOR, ".terminal-results-table th")
    RESULTS_TABLE_ROWS = (By.CSS_SELECTOR, ".terminal-results-table tbody tr")

    PRESET_BTNS = (By.CSS_SELECTOR, ".terminal-body .btn-action[data-query]")
    PRESET_COUNTRY_PERF = (By.CSS_SELECTOR, ".terminal-body button[data-query*='mart_country_performance']")
    PRESET_CREDIT_FUNNEL = (By.CSS_SELECTOR, ".terminal-body button[data-query*='mart_credit_funnel']")
    PRESET_QUALITY_ISSUES = (By.CSS_SELECTOR, ".terminal-body button[data-query*='quality_issues']")
    PRESET_CUSTOMER_FEATURES = (By.CSS_SELECTOR, ".terminal-body button[data-query*='mart_customer_features']")

    # Footer Links
    FOOTER_REPO_LINK = (By.CSS_SELECTOR, "a[href='https://github.com/AmosAlloyce/FinPulse']")
    FOOTER_COCKPIT_LINK = (By.CSS_SELECTOR, "a[href='/finpulse']")
