from finpulse.config import Settings


def test_settings_parses_comma_separated_countries_from_env(monkeypatch):
    monkeypatch.setenv("FINPULSE_COUNTRIES", "KEN,UGA,GHA,TZA,ZMB")
    settings = Settings()

    assert settings.countries == ["KEN", "UGA", "GHA", "TZA", "ZMB"]
