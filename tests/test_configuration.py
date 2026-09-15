from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.core.logging import get_logger


def test_configuration_values():
    assert settings.app_name == "Adaptive Interview Simulator"
    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"


def test_interview_configuration():
    assert settings.min_interview_turns == 8
    assert settings.max_interview_turns == 12
    assert settings.min_interview_turns <= settings.max_interview_turns


def test_application_error():
    error = ApplicationError(
        "Interview was not found",
        "INTERVIEW_NOT_FOUND",
    )

    assert error.message == "Interview was not found"
    assert error.code == "INTERVIEW_NOT_FOUND"
    assert str(error) == "Interview was not found"


def test_logger_creation():
    logger = get_logger("test.configuration")

    assert logger.name == "test.configuration"