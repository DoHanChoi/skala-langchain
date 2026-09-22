"""SQLAlchemy models for the fixed RoleLens analytics schema."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


SCHEMA = "analytics"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA}

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    signup_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    age: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    acquisition_channel: Mapped[str] = mapped_column(String(20), nullable=False)
    device: Mapped[str] = mapped_column(String(20), nullable=False)

    events: Mapped[list[UserEvent]] = relationship(back_populates="user")
    orders: Mapped[list[Order]] = relationship(back_populates="user")


class UserEvent(Base):
    __tablename__ = "user_events"
    __table_args__ = {"schema": SCHEMA}

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.user_id"), nullable=False, index=True
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(30), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)

    user: Mapped[User] = relationship(back_populates="events")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": SCHEMA}

    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    list_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    orders: Mapped[list[Order]] = relationship(back_populates="product")


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = {"schema": SCHEMA}

    campaign_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    campaign_name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    orders: Mapped[list[Order]] = relationship(back_populates="campaign")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": SCHEMA}

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.user_id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.product_id"), nullable=False, index=True
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.campaigns.campaign_id"), nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sales_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    user: Mapped[User] = relationship(back_populates="orders")
    product: Mapped[Product] = relationship(back_populates="orders")
    campaign: Mapped[Campaign | None] = relationship(back_populates="orders")


class MonthlyTarget(Base):
    __tablename__ = "monthly_targets"
    __table_args__ = {"schema": SCHEMA}

    target_month: Mapped[date] = mapped_column(Date, primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(30), primary_key=True)
    target_value: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    persona_owner: Mapped[str] = mapped_column(String(20), nullable=False)
