"""Create the RoleLens analytics schema and read-only grants."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("signup_date", sa.Date(), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("region", sa.String(20), nullable=False),
        sa.Column("acquisition_channel", sa.String(20), nullable=False),
        sa.Column("device", sa.String(20), nullable=False),
        sa.CheckConstraint("age BETWEEN 14 AND 80", name="ck_users_age"),
        schema="analytics",
    )
    op.create_index("ix_users_signup_date", "users", ["signup_date"], schema="analytics")

    op.create_table(
        "user_events",
        sa.Column("event_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("analytics.users.user_id"),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_name", sa.String(30), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "event_name IN ('app_open','product_view','add_to_cart','checkout_start','feature_used')",
            name="ck_user_events_name",
        ),
        schema="analytics",
    )
    op.create_index("ix_user_events_user_id", "user_events", ["user_id"], schema="analytics")
    op.create_index("ix_user_events_event_date", "user_events", ["event_date"], schema="analytics")

    op.create_table(
        "products",
        sa.Column("product_id", sa.BigInteger(), primary_key=True),
        sa.Column("product_name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("list_price", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("list_price >= 0", name="ck_products_list_price"),
        sa.CheckConstraint(
            "category IN ('beauty','fashion','food','living','digital')",
            name="ck_products_category",
        ),
        schema="analytics",
    )
    op.create_index("ix_products_category", "products", ["category"], schema="analytics")

    op.create_table(
        "campaigns",
        sa.Column("campaign_id", sa.BigInteger(), primary_key=True),
        sa.Column("campaign_name", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("spend", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_campaigns_dates"),
        sa.CheckConstraint("spend >= 0", name="ck_campaigns_spend"),
        sa.CheckConstraint(
            "channel IN ('search','social','display','crm')",
            name="ck_campaigns_channel",
        ),
        schema="analytics",
    )

    op.create_table(
        "orders",
        sa.Column("order_id", sa.BigInteger(), primary_key=True),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("analytics.users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("analytics.products.product_id"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.BigInteger(),
            sa.ForeignKey("analytics.campaigns.campaign_id"),
            nullable=True,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("sales_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("quantity >= 1", name="ck_orders_quantity"),
        sa.CheckConstraint("sales_amount >= 0", name="ck_orders_sales_amount"),
        sa.CheckConstraint(
            "status IN ('completed','cancelled','refunded')",
            name="ck_orders_status",
        ),
        schema="analytics",
    )
    for column in ("order_date", "user_id", "product_id", "campaign_id", "status"):
        op.create_index(f"ix_orders_{column}", "orders", [column], schema="analytics")

    op.create_table(
        "monthly_targets",
        sa.Column("target_month", sa.Date(), primary_key=True),
        sa.Column("metric_name", sa.String(30), primary_key=True),
        sa.Column("target_value", sa.Numeric(16, 2), nullable=False),
        sa.Column("persona_owner", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "metric_name IN ('revenue','new_customers')",
            name="ck_monthly_targets_metric",
        ),
        sa.CheckConstraint("target_value >= 0", name="ck_monthly_targets_value"),
        schema="analytics",
    )

    op.execute("GRANT USAGE ON SCHEMA analytics TO rolelens_agent_ro")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO rolelens_agent_ro")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics "
        "GRANT SELECT ON TABLES TO rolelens_agent_ro"
    )


def downgrade() -> None:
    for table in (
        "monthly_targets",
        "orders",
        "campaigns",
        "products",
        "user_events",
        "users",
    ):
        op.drop_table(table, schema="analytics")
    op.execute("DROP SCHEMA IF EXISTS analytics")
