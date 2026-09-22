from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from rolelens.db.engine import create_admin_engine, create_readonly_engine
from rolelens.db.repository import AnalyticsRepository, QueryExecutionError
from rolelens.db.seed import seed_database


pytestmark = pytest.mark.integration


def test_seed_is_idempotent(require_postgres) -> None:  # noqa: ANN001
    first = seed_database(seed=42, settings=require_postgres)
    second = seed_database(seed=42, settings=require_postgres)
    assert first == second == {
        "users": 1200,
        "user_events": 5203,
        "products": 25,
        "campaigns": 84,
        "orders": 3907,
        "monthly_targets": 42,
    }


def test_seed_values_are_reproducible(require_postgres) -> None:  # noqa: ANN001
    engine = create_admin_engine(require_postgres)

    def snapshot() -> tuple:
        with engine.connect() as connection:
            return (
                connection.execute(
                    text(
                        "SELECT COUNT(*), MIN(order_date), MAX(order_date), "
                        "SUM(sales_amount) FILTER (WHERE status = 'completed') "
                        "FROM analytics.orders"
                    )
                ).one(),
                connection.execute(
                    text(
                        "SELECT COUNT(*), MIN(event_date), MAX(event_date), "
                        "COUNT(*) FILTER (WHERE event_name = 'feature_used') "
                        "FROM analytics.user_events"
                    )
                ).one(),
                connection.execute(
                    text(
                        "SELECT COUNT(*), SUM(target_value) "
                        "FROM analytics.monthly_targets"
                    )
                ).one(),
            )

    first = snapshot()
    seed_database(seed=42, settings=require_postgres)
    assert snapshot() == first


def test_schema_keys_dates_categories_and_foreign_keys(require_postgres) -> None:  # noqa: ANN001
    engine = create_admin_engine(require_postgres)
    schema_inspector = inspect(engine)
    assert schema_inspector.get_pk_constraint("monthly_targets", schema="analytics")[
        "constrained_columns"
    ] == ["target_month", "metric_name"]
    assert schema_inspector.get_pk_constraint("orders", schema="analytics")[
        "constrained_columns"
    ] == ["order_id"]

    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM analytics.user_events e "
                "LEFT JOIN analytics.users u USING (user_id) WHERE u.user_id IS NULL"
            )
        ).scalar_one() == 0
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM analytics.orders o "
                "LEFT JOIN analytics.users u USING (user_id) "
                "LEFT JOIN analytics.products p USING (product_id) "
                "LEFT JOIN analytics.campaigns c USING (campaign_id) "
                "WHERE u.user_id IS NULL OR p.product_id IS NULL "
                "OR (o.campaign_id IS NOT NULL AND c.campaign_id IS NULL)"
            )
        ).scalar_one() == 0
        assert connection.execute(
            text(
                "SELECT MIN(signup_date), MAX(signup_date) FROM analytics.users"
            )
        ).one() == (date(2025, 1, 1), date(2026, 9, 14))
        assert connection.execute(
            text("SELECT MIN(event_date), MAX(event_date) FROM analytics.user_events")
        ).one() == (date(2025, 1, 1), date(2026, 9, 15))
        assert connection.execute(
            text("SELECT MIN(order_date), MAX(order_date) FROM analytics.orders")
        ).one() == (date(2025, 1, 9), date(2026, 9, 15))
        assert set(
            connection.execute(
                text("SELECT DISTINCT category FROM analytics.products")
            ).scalars()
        ) == {"beauty", "fashion", "food", "living", "digital"}
        assert set(
            connection.execute(
                text("SELECT DISTINCT status FROM analytics.orders")
            ).scalars()
        ) == {"completed", "cancelled", "refunded"}
        assert set(
            connection.execute(
                text("SELECT DISTINCT device FROM analytics.users")
            ).scalars()
        ) == {"mobile", "desktop", "tablet"}


def test_allowlisted_metadata_and_row_cap(require_postgres) -> None:  # noqa: ANN001
    repository = AnalyticsRepository(settings=require_postgres)
    assert {item["name"] for item in repository.list_tables()} == {
        "users", "user_events", "products", "campaigns", "orders", "monthly_targets"
    }
    artifact = repository.execute_readonly_sql(
        "SELECT order_id FROM analytics.orders ORDER BY order_id"
    )
    assert artifact.row_count == 100
    assert artifact.rows[0]["order_id"] == 1


def test_reference_sql_baselines(require_postgres) -> None:  # noqa: ANN001
    repository = AnalyticsRepository(settings=require_postgres)
    root = Path(__file__).resolve().parents[2]
    planner = repository.execute_readonly_sql(
        (root / "sql/reference/ts01_planner_target.sql").read_text()
    )
    marketer = repository.execute_readonly_sql(
        (root / "sql/reference/ts02_marketer_twenty_category.sql").read_text()
    )
    pm = repository.execute_readonly_sql(
        (root / "sql/reference/ts03_pm_activation.sql").read_text()
    )
    assert planner.row_count == 3
    assert {float(row["achievement_rate"]) for row in planner.rows} == {95.69}
    actual = sum(float(row["actual_revenue"]) for row in planner.rows)
    target = sum(float(row["target_revenue"]) for row in planner.rows)
    assert actual / target * 100 == pytest.approx(95.69, abs=0.01)
    beauty = next(row for row in marketer.rows if row["category"] == "beauty" and row["period"] == "current")
    assert float(beauty["revenue"]) == pytest.approx(9_224_188.55)
    rates = {row["device"]: float(row["activation_rate"]) for row in pm.rows}
    assert rates == {"desktop": 61.70, "mobile": 43.06, "tablet": 66.67}


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM analytics.orders WHERE order_id = -1",
        "CREATE TABLE analytics.should_not_exist(id integer)",
    ],
)
def test_readonly_role_rejects_ddl_and_dml(require_postgres, statement: str) -> None:  # noqa: ANN001
    with create_readonly_engine(require_postgres).connect() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(text(statement))


def test_statement_timeout(require_postgres) -> None:  # noqa: ANN001
    repository = AnalyticsRepository(settings=require_postgres)
    with pytest.raises(QueryExecutionError) as exc_info:
        repository.execute_readonly_sql(
            "SELECT COUNT(o1.order_id) AS huge_count "
            "FROM analytics.orders AS o1 "
            "CROSS JOIN analytics.orders AS o2 "
            "CROSS JOIN analytics.orders AS o3"
        )
    assert exc_info.value.category == "timeout"
