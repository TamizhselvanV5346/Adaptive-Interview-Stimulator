from app.core.config import settings


def test_required_foundation_settings_exist():
    assert settings.app_name == "Adaptive Interview Simulator"
    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.min_interview_turns == 8