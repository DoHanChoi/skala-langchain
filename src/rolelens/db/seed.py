"""Deterministic Mock commerce data generator and loader."""

from __future__ import annotations

import calendar
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import Engine, func, insert, select, text
from sqlalchemy.orm import Session

from rolelens.config import Settings, get_settings
from rolelens.db.engine import create_admin_engine
from rolelens.db.models import Campaign, MonthlyTarget, Order, Product, User, UserEvent


CATEGORIES = ("beauty", "fashion", "food", "living", "digital")
REGIONS = ("서울", "경기", "부산", "대구", "기타")
ACQUISITION_CHANNELS = ("organic", "search", "social", "display", "referral")
DEVICES = ("mobile", "desktop", "tablet")
CAMPAIGN_CHANNELS = ("search", "social", "display", "crm")
EVENT_NAMES = ("app_open", "product_view", "add_to_cart", "checkout_start", "feature_used")
ORDER_STATUSES = ("completed", "cancelled", "refunded")


@dataclass(frozen=True)
class SeedDataset:
    users: list[dict[str, Any]]
    events: list[dict[str, Any]]
    products: list[dict[str, Any]]
    campaigns: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    targets: list[dict[str, Any]]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "users": len(self.users),
            "user_events": len(self.events),
            "products": len(self.products),
            "campaigns": len(self.campaigns),
            "orders": len(self.orders),
            "monthly_targets": len(self.targets),
        }


def _month_starts(start: date, end: date) -> Iterable[date]:
    current = date(start.year, start.month, 1)
    while current <= end:
        yield current
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def _random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _weighted_choice(rng: random.Random, values: tuple[str, ...], weights: list[float]) -> str:
    return rng.choices(values, weights=weights, k=1)[0]


def build_seed_dataset(seed: int = 42, data_as_of: date = date(2026, 9, 15)) -> SeedDataset:
    """Build deterministic synthetic rows with documented learning patterns."""

    rng = random.Random(seed)
    start = date(2025, 1, 1)

    products: list[dict[str, Any]] = []
    category_prices = {
        "beauty": 32_000,
        "fashion": 58_000,
        "food": 21_000,
        "living": 47_000,
        "digital": 125_000,
    }
    for category_index, category in enumerate(CATEGORIES):
        for item_index in range(1, 6):
            product_id = category_index * 5 + item_index
            products.append(
                {
                    "product_id": product_id,
                    "product_name": f"{category.title()} Mock {item_index}",
                    "category": category,
                    "list_price": _money(category_prices[category] * (0.75 + item_index * 0.12)),
                }
            )
    product_by_category = {
        category: [p for p in products if p["category"] == category] for category in CATEGORIES
    }

    campaigns: list[dict[str, Any]] = []
    campaign_by_month_channel: dict[tuple[date, str], int] = {}
    campaign_id = 1
    for month in _month_starts(start, data_as_of):
        end_day = calendar.monthrange(month.year, month.month)[1]
        month_end = min(date(month.year, month.month, end_day), data_as_of)
        for channel in CAMPAIGN_CHANNELS:
            campaigns.append(
                {
                    "campaign_id": campaign_id,
                    "campaign_name": f"{month:%Y-%m} {channel} mock campaign",
                    "channel": channel,
                    "start_date": month,
                    "end_date": month_end,
                    "spend": _money(rng.randint(2_000_000, 8_000_000)),
                }
            )
            campaign_by_month_channel[(month, channel)] = campaign_id
            campaign_id += 1

    users: list[dict[str, Any]] = []
    for user_id in range(1, 1201):
        signup_date = _random_date(rng, start, data_as_of)
        if signup_date >= date(2026, 8, 1):
            channel_weights = [0.38, 0.27, 0.06, 0.12, 0.17]
        else:
            channel_weights = [0.25, 0.23, 0.24, 0.13, 0.15]
        users.append(
            {
                "user_id": user_id,
                "signup_date": signup_date,
                "age": rng.randint(18, 64),
                "region": _weighted_choice(rng, REGIONS, [0.31, 0.28, 0.13, 0.09, 0.19]),
                "acquisition_channel": _weighted_choice(
                    rng, ACQUISITION_CHANNELS, channel_weights
                ),
                "device": _weighted_choice(rng, DEVICES, [0.64, 0.27, 0.09]),
            }
        )

    events: list[dict[str, Any]] = []
    event_id = 1
    activation_probability = {"mobile": 0.43, "desktop": 0.67, "tablet": 0.53}
    for user in users:
        signup = user["signup_date"]

        def add_event(event_date: date, event_name: str, suffix: int) -> None:
            nonlocal event_id
            if event_date <= data_as_of:
                events.append(
                    {
                        "event_id": event_id,
                        "user_id": user["user_id"],
                        "event_date": event_date,
                        "event_name": event_name,
                        "session_id": f"s-{user['user_id']}-{suffix}",
                    }
                )
                event_id += 1

        add_event(signup, "app_open", 0)
        add_event(min(signup + timedelta(days=rng.randint(0, 5)), data_as_of), "product_view", 1)
        if rng.random() < 0.72:
            add_event(min(signup + timedelta(days=rng.randint(1, 12)), data_as_of), "add_to_cart", 2)
        if rng.random() < 0.52:
            add_event(min(signup + timedelta(days=rng.randint(1, 18)), data_as_of), "checkout_start", 3)
        if rng.random() < activation_probability[user["device"]]:
            add_event(signup + timedelta(days=rng.randint(0, 7)), "feature_used", 4)
        if signup + timedelta(days=30) <= data_as_of and rng.random() < 0.65:
            add_event(signup + timedelta(days=rng.randint(8, 30)), "app_open", 5)

    orders: list[dict[str, Any]] = []
    order_id = 1

    def choose_product(user: dict[str, Any], order_date: date) -> dict[str, Any]:
        if 20 <= user["age"] < 30 and order_date >= date(2026, 7, 1):
            weights = [0.48, 0.17, 0.13, 0.12, 0.10]
        elif 20 <= user["age"] < 30 and date(2026, 4, 1) <= order_date < date(2026, 7, 1):
            weights = [0.14, 0.28, 0.21, 0.17, 0.20]
        else:
            weights = [0.19, 0.22, 0.23, 0.19, 0.17]
        category = _weighted_choice(rng, CATEGORIES, weights)
        return rng.choice(product_by_category[category])

    def append_order(user: dict[str, Any], order_date: date, force_completed: bool = False) -> None:
        nonlocal order_id
        product = choose_product(user, order_date)
        quantity = rng.choices([1, 2, 3], weights=[0.75, 0.20, 0.05], k=1)[0]
        status = "completed" if force_completed else _weighted_choice(
            rng, ORDER_STATUSES, [0.88, 0.07, 0.05]
        )
        campaign_id_value: int | None = None
        if rng.random() < 0.47:
            channel = rng.choice(CAMPAIGN_CHANNELS)
            campaign_month = date(order_date.year, order_date.month, 1)
            campaign_id_value = campaign_by_month_channel[(campaign_month, channel)]
        discount = rng.uniform(0.84, 1.0)
        orders.append(
            {
                "order_id": order_id,
                "order_date": order_date,
                "user_id": user["user_id"],
                "product_id": product["product_id"],
                "campaign_id": campaign_id_value,
                "quantity": quantity,
                "sales_amount": _money(product["list_price"] * quantity * Decimal(str(discount))),
                "status": status,
            }
        )
        order_id += 1

    for user in users:
        if rng.random() >= 0.88:
            continue
        first_order = user["signup_date"] + timedelta(days=rng.randint(0, 45))
        if first_order > data_as_of:
            continue
        append_order(user, first_order, force_completed=True)
        for _ in range(rng.randint(0, 5)):
            append_order(user, _random_date(rng, first_order, data_as_of))

    current_twenty_users = [
        user
        for user in users
        if 20 <= user["age"] < 30 and user["signup_date"] <= date(2026, 7, 1)
    ]
    for _ in range(260):
        append_order(
            rng.choice(current_twenty_users),
            _random_date(rng, date(2026, 7, 1), data_as_of),
            force_completed=True,
        )

    append_order(users[0], data_as_of, force_completed=True)

    revenue_by_month: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    first_completed_order: dict[int, date] = {}
    for order in orders:
        if order["status"] != "completed":
            continue
        month = date(order["order_date"].year, order["order_date"].month, 1)
        revenue_by_month[month] += order["sales_amount"]
        first_completed_order[order["user_id"]] = min(
            order["order_date"], first_completed_order.get(order["user_id"], order["order_date"])
        )
    new_customers_by_month: dict[date, int] = defaultdict(int)
    for first_date in first_completed_order.values():
        new_customers_by_month[date(first_date.year, first_date.month, 1)] += 1

    targets: list[dict[str, Any]] = []
    for month in _month_starts(start, data_as_of):
        is_q3_2026 = month.year == 2026 and month.month in (7, 8, 9)
        revenue_factor = Decimal("1.045") if is_q3_2026 else Decimal("1.02")
        targets.extend(
            [
                {
                    "target_month": month,
                    "metric_name": "revenue",
                    "target_value": _money(revenue_by_month[month] * revenue_factor),
                    "persona_owner": "planner",
                },
                {
                    "target_month": month,
                    "metric_name": "new_customers",
                    "target_value": _money(
                        Decimal(new_customers_by_month[month]) * Decimal("1.05")
                    ),
                    "persona_owner": "planner",
                },
            ]
        )

    return SeedDataset(users, events, products, campaigns, orders, targets)


def _assert_migrated(engine: Engine) -> None:
    with engine.connect() as connection:
        exists = connection.execute(text("SELECT to_regclass('analytics.users')")).scalar_one()
    if exists is None:
        raise RuntimeError("analytics schema is missing; run `alembic upgrade head` first")


def seed_database(
    seed: int | None = None,
    data_as_of: date | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Replace all Mock rows in FK-safe order and verify persisted counts."""

    settings = settings or get_settings()
    dataset = build_seed_dataset(
        seed=settings.random_seed if seed is None else seed,
        data_as_of=settings.data_as_of if data_as_of is None else data_as_of,
    )
    engine = create_admin_engine(settings)
    _assert_migrated(engine)

    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "TRUNCATE TABLE analytics.user_events, analytics.orders, "
                "analytics.monthly_targets, analytics.campaigns, analytics.products, "
                "analytics.users RESTART IDENTITY CASCADE"
            )
        )
        session.execute(insert(User), dataset.users)
        session.execute(insert(Product), dataset.products)
        session.execute(insert(Campaign), dataset.campaigns)
        session.execute(insert(UserEvent), dataset.events)
        session.execute(insert(Order), dataset.orders)
        session.execute(insert(MonthlyTarget), dataset.targets)

    persisted: dict[str, int] = {}
    with Session(engine) as session:
        for name, model in (
            ("users", User),
            ("user_events", UserEvent),
            ("products", Product),
            ("campaigns", Campaign),
            ("orders", Order),
            ("monthly_targets", MonthlyTarget),
        ):
            persisted[name] = session.scalar(select(func.count()).select_from(model)) or 0
    if persisted != dataset.counts:
        raise RuntimeError(f"seed count verification failed: {persisted} != {dataset.counts}")
    return persisted
