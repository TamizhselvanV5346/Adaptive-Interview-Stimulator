import pytest

from app.database.session import engine


@pytest.fixture(scope="session", autouse=True)
def reset_database_engine():
    yield
    # Engine cleanup is handled after the complete pytest session.