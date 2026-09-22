from __future__ import annotations

import pytest

from rolelens.db.safety import UnsafeSQL, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE analytics.orders",
        "DELETE FROM analytics.orders",
        "UPDATE analytics.orders SET quantity = 2",
        "SELECT * FROM analytics.orders",
        "SELECT order_id FROM analytics.orders; DROP TABLE analytics.orders",
        "SELECT table_name FROM information_schema.tables",
        "SELECT relname FROM pg_catalog.pg_class",
        "SELECT order_id FROM public.orders",
        "SELECT secret FROM analytics.secrets",
        "SELECT current_setting('server_version') AS server_version",
        "SELECT pg_read_file('/etc/passwd') AS contents",
        "WITH changed AS (DELETE FROM analytics.orders RETURNING order_id) SELECT order_id FROM changed",
        "SELECT order_id INTO public.order_copy FROM analytics.orders",
        "SELECT order_id FROM analytics.orders FOR UPDATE",
        "COPY analytics.orders TO STDOUT",
        "CALL analytics.refresh_orders()",
        "SELECT pg_read_file('/etc/passwd') AS contents FROM analytics.orders",
        "SELECT order_id FROM analytics.orders LIMIT 0",
    ],
)
def test_dangerous_sql_is_blocked(sql: str) -> None:
    with pytest.raises(UnsafeSQL):
        validate_sql(sql)


def test_count_star_is_allowed_but_projection_star_is_not() -> None:
    validated = validate_sql("SELECT COUNT(*) AS order_count FROM analytics.orders")
    assert validated.source_tables == ("orders",)


def test_row_limit_is_added_and_capped() -> None:
    added = validate_sql("SELECT order_id FROM analytics.orders")
    capped = validate_sql("SELECT order_id FROM analytics.orders LIMIT 999")
    assert "LIMIT 100" in added.sql
    assert "LIMIT 100" in capped.sql


def test_cte_alias_is_not_treated_as_physical_table() -> None:
    validated = validate_sql(
        "WITH completed AS (SELECT order_id FROM analytics.orders WHERE status='completed') "
        "SELECT order_id FROM completed"
    )
    assert validated.source_tables == ("orders",)
