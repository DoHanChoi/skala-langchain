"""SQLAlchemy engine factories with connection-level safety controls."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event

from rolelens.config import Settings, get_settings


def create_admin_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_engine(settings.admin_url(), pool_pre_ping=True)


def create_readonly_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    engine = create_engine(
        settings.readonly_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_readonly_session(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")
            cursor.execute("SET search_path = analytics")
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, false)",
                (str(settings.sql_statement_timeout_ms),),
            )

    return engine
