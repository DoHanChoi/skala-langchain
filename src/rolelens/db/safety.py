"""PostgreSQL AST validation for the SQL execution boundary."""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


ALLOWED_SCHEMA = "analytics"
ALLOWED_TABLES = frozenset(
    {"users", "user_events", "products", "campaigns", "orders", "monthly_targets"}
)
FORBIDDEN_SCHEMAS = frozenset({"information_schema", "pg_catalog", "public"})
FORBIDDEN_FUNCTIONS = frozenset(
    {
        "current_setting",
        "database_to_xml",
        "lo_export",
        "lo_import",
        "query_to_xml",
        "set_config",
        "version",
    }
)


class UnsafeSQL(ValueError):
    """Raised before DB access when a query violates the read-only policy."""


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    source_tables: tuple[str, ...]


def _disallowed_expression_types() -> tuple[type[exp.Expression], ...]:
    names = (
        "Insert",
        "Update",
        "Delete",
        "Create",
        "Drop",
        "Alter",
        "Command",
        "Merge",
        "Copy",
        "Transaction",
        "Commit",
        "Rollback",
        "Grant",
        "Revoke",
        "Lock",
        "Into",
    )
    return tuple(getattr(exp, name) for name in names if hasattr(exp, name))


def _contains_projection_star(root: exp.Expression) -> bool:
    for star in root.find_all(exp.Star):
        if isinstance(star.parent, exp.Count):
            continue
        return True
    return False


def _physical_tables(root: exp.Expression) -> tuple[str, ...]:
    cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    tables: set[str] = set()
    for table in root.find_all(exp.Table):
        table_name = table.name.lower()
        schema = (table.db or "").lower()
        if not schema and table_name in cte_names:
            continue
        if schema in FORBIDDEN_SCHEMAS:
            raise UnsafeSQL(f"허용되지 않은 스키마입니다: {schema}")
        if schema != ALLOWED_SCHEMA:
            raise UnsafeSQL("모든 물리 테이블은 analytics 스키마를 명시해야 합니다.")
        if table_name not in ALLOWED_TABLES:
            raise UnsafeSQL(f"allowlist 밖의 테이블입니다: {table_name}")
        tables.add(table_name)
    return tuple(sorted(tables))


def _reject_forbidden_functions(root: exp.Expression) -> None:
    for function in root.find_all(exp.Anonymous):
        name = function.name.lower()
        if name.startswith("pg_") or name.startswith("dblink") or name in FORBIDDEN_FUNCTIONS:
            raise UnsafeSQL(f"허용되지 않은 DB 함수입니다: {name}")


def _apply_row_limit(root: exp.Expression, max_rows: int) -> exp.Expression:
    limited = root.copy()
    limit = limited.args.get("limit")
    if limit is not None:
        expression = limit.expression
        if isinstance(expression, exp.Literal) and expression.is_int:
            value = int(expression.this)
            if value <= 0:
                raise UnsafeSQL("LIMIT은 양의 정수여야 합니다.")
            if value <= max_rows:
                return limited
        else:
            raise UnsafeSQL("LIMIT은 고정된 양의 정수여야 합니다.")
    return limited.limit(max_rows)


def validate_sql(sql: str, max_rows: int = 100) -> ValidatedSQL:
    """Allow exactly one SELECT/query expression over fixed analytics tables."""

    if not sql or not sql.strip():
        raise UnsafeSQL("빈 SQL은 실행할 수 없습니다.")
    try:
        statements = [item for item in sqlglot.parse(sql, read="postgres") if item is not None]
    except ParseError as exc:
        raise UnsafeSQL("PostgreSQL SQL을 파싱할 수 없습니다.") from exc
    if len(statements) != 1:
        raise UnsafeSQL("정확히 하나의 SQL statement만 허용됩니다.")

    root = statements[0]
    if not isinstance(root, exp.Query):
        raise UnsafeSQL("SELECT 또는 WITH ... SELECT 조회만 허용됩니다.")
    if any(isinstance(node, _disallowed_expression_types()) for node in root.walk()):
        raise UnsafeSQL("DDL, DML, COPY, 권한 변경, lock 명령은 허용되지 않습니다.")
    if _contains_projection_star(root):
        raise UnsafeSQL("SELECT *는 허용되지 않습니다. 필요한 컬럼을 명시하세요.")

    _reject_forbidden_functions(root)
    source_tables = _physical_tables(root)
    if not source_tables:
        raise UnsafeSQL("최소 하나의 allowlist analytics 테이블을 조회해야 합니다.")
    limited = _apply_row_limit(root, max_rows)
    return ValidatedSQL(
        sql=limited.sql(dialect="postgres", pretty=True),
        source_tables=source_tables,
    )
