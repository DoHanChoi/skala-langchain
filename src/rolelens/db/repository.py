"""Allowlisted metadata and query repository over the read-only connection."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from rolelens.config import Settings, get_settings
from rolelens.db.engine import create_readonly_engine
from rolelens.db.safety import ALLOWED_SCHEMA, ALLOWED_TABLES, UnsafeSQL, validate_sql
from rolelens.domain.models import QueryArtifact


TABLE_DESCRIPTIONS = {
    "users": "가입일·연령·지역·유입채널·기기를 가진 Mock 사용자",
    "user_events": "사용자의 앱 오픈·상품 조회·구매 퍼널·핵심 기능 이벤트",
    "products": "Mock 상품명·카테고리·표준가",
    "campaigns": "Mock 캠페인·매체·기간·비용",
    "orders": "상품 1개를 대표하는 Mock 주문·매출·상태",
    "monthly_targets": "planner 월별 매출·신규 고객 목표",
}

DATE_COLUMNS = {
    "users": "signup_date",
    "user_events": "event_date",
    "campaigns": "end_date",
    "orders": "order_date",
    "monthly_targets": "target_month",
}


class QueryExecutionError(RuntimeError):
    def __init__(self, category: str, safe_message: str):
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message


def _safe_database_error(exc: DBAPIError) -> QueryExecutionError:
    original = getattr(exc, "orig", None)
    sqlstate = getattr(original, "sqlstate", None)
    if sqlstate == "57014":
        return QueryExecutionError("timeout", "SQL 실행 시간이 제한을 초과했습니다.")
    if sqlstate in {"42601", "42703", "42P01"}:
        return QueryExecutionError("retryable_sql", "SQL 문법 또는 스키마·컬럼을 확인해야 합니다.")
    if sqlstate in {"42501", "25006"}:
        return QueryExecutionError("permission", "읽기 전용 정책으로 해당 SQL이 거부됐습니다.")
    return QueryExecutionError("database", "PostgreSQL 조회 중 오류가 발생했습니다.")


class AnalyticsRepository:
    def __init__(self, engine: Engine | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.engine = engine or create_readonly_engine(self.settings)

    def list_tables(self) -> list[dict[str, str]]:
        try:
            actual = set(inspect(self.engine).get_table_names(schema=ALLOWED_SCHEMA))
        except SQLAlchemyError as exc:
            raise QueryExecutionError("connection", "PostgreSQL에 연결할 수 없습니다.") from exc
        return [
            {"name": name, "description": TABLE_DESCRIPTIONS[name]}
            for name in sorted(actual & ALLOWED_TABLES)
        ]

    def inspect_schema(self, table_names: list[str]) -> list[dict[str, Any]]:
        requested = {name.lower() for name in table_names}
        unknown = requested - ALLOWED_TABLES
        if unknown:
            raise UnsafeSQL(f"allowlist 밖의 테이블입니다: {', '.join(sorted(unknown))}")
        inspector = inspect(self.engine)
        available = set(inspector.get_table_names(schema=ALLOWED_SCHEMA))
        result: list[dict[str, Any]] = []
        for name in sorted(requested):
            if name not in available:
                raise QueryExecutionError("schema", f"analytics.{name} 테이블이 없습니다.")
            columns = [
                {"name": column["name"], "type": str(column["type"]), "nullable": column["nullable"]}
                for column in inspector.get_columns(name, schema=ALLOWED_SCHEMA)
            ]
            result.append(
                {
                    "name": name,
                    "description": TABLE_DESCRIPTIONS[name],
                    "columns": columns,
                    "primary_key": inspector.get_pk_constraint(name, schema=ALLOWED_SCHEMA).get(
                        "constrained_columns", []
                    ),
                    "foreign_keys": inspector.get_foreign_keys(name, schema=ALLOWED_SCHEMA),
                }
            )
        return result

    def _data_as_of(self, connection, source_tables: tuple[str, ...]) -> date:  # noqa: ANN001
        maxima: list[date] = []
        for table_name in source_tables:
            column = DATE_COLUMNS.get(table_name)
            if not column:
                continue
            value = connection.execute(
                text(f"SELECT MAX({column}) FROM analytics.{table_name}")
            ).scalar_one()
            if isinstance(value, date):
                maxima.append(value)
        return max(maxima, default=self.settings.data_as_of)

    def execute_readonly_sql(self, sql: str, attempts: int = 1) -> QueryArtifact:
        validated = validate_sql(sql, max_rows=self.settings.max_query_rows)
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(validated.sql))
                columns = list(result.keys())
                rows = [dict(row) for row in result.mappings().all()]
                data_as_of = self._data_as_of(connection, validated.source_tables)
        except DBAPIError as exc:
            raise _safe_database_error(exc) from exc
        except SQLAlchemyError as exc:
            raise QueryExecutionError("connection", "PostgreSQL에 연결할 수 없습니다.") from exc
        return QueryArtifact(
            sql=validated.sql,
            columns=columns,
            rows=rows,
            source_tables=list(validated.source_tables),
            row_count=len(rows),
            data_as_of=data_as_of,
            attempts=attempts,
        )
