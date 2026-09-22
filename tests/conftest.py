from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from rolelens.config import Settings
from rolelens.db.engine import create_admin_engine


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture(scope="session")
def require_postgres(settings: Settings) -> Settings:
    try:
        with create_admin_engine(settings).connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"RoleLens PostgreSQL is not available: {type(exc).__name__}")
    return settings
