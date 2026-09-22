"""Shared metric definitions and deterministic calculations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd

from rolelens.domain.models import ComputedMetric, QueryArtifact


METRIC_DEFINITIONS: dict[str, str] = {
    "revenue": "completed 상태 주문의 sales_amount 합계(취소·환불 제외)",
    "orders": "completed 상태의 고유 주문 수",
    "customers": "completed 주문을 발생시킨 고유 사용자 수",
    "new_customers": "첫 completed 주문일이 분석 기간 내인 고객 수",
    "average_order_value": "completed 매출액 / completed 주문 수",
    "active_users": "분석 기간 user_events가 1건 이상인 고유 사용자 수",
    "activation_rate_7d": "관찰 가능한 가입자 중 가입일로부터 7일 이내 feature_used 사용자 비율",
    "purchase_conversion_rate": "분석 기간 completed 구매 고객 / 활성 사용자",
    "campaign_roas": "캠페인 귀속 completed 매출 / 캠페인 spend",
    "target_achievement_rate": "실제 지표 / 목표값 * 100",
}


def artifact_to_dataframe(artifact: QueryArtifact) -> pd.DataFrame:
    frame = pd.DataFrame(artifact.rows, columns=artifact.columns)
    for column in frame.columns:
        if frame[column].map(lambda value: isinstance(value, Decimal)).any():
            frame[column] = frame[column].map(
                lambda value: float(value) if isinstance(value, Decimal) else value
            )
    return frame


def safe_ratio(numerator: float, denominator: float, multiplier: float = 1.0) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator * multiplier


def period_growth(current: float, previous: float) -> float | None:
    return safe_ratio(current - previous, previous, 100.0)


def target_achievement(actual: float, target: float) -> float | None:
    return safe_ratio(actual, target, 100.0)


def conversion_rate(converted: float, eligible: float) -> float | None:
    return safe_ratio(converted, eligible, 100.0)


def share(value: float, total: float) -> float | None:
    return safe_ratio(value, total, 100.0)


def rank_values(values: Iterable[float], descending: bool = True) -> list[int]:
    series = pd.Series(list(values), dtype=float)
    return series.rank(method="dense", ascending=not descending).astype(int).tolist()


def _metric(name: str, value: Any, formula: str, unit: str | None = None, **context: Any) -> ComputedMetric:
    if isinstance(value, float):
        value = round(value, 2)
    return ComputedMetric(name=name, value=value, formula=formula, unit=unit, context=context)


def analyze_result(frame: pd.DataFrame) -> list[ComputedMetric]:
    """Produce named evidence calculations for supported and generic result shapes."""

    if frame.empty:
        return []
    columns = set(frame.columns)
    metrics: list[ComputedMetric] = []

    if {"actual_revenue", "target_revenue"} <= columns:
        actual = float(frame["actual_revenue"].sum())
        target = float(frame["target_revenue"].sum())
        metrics.extend(
            [
                _metric("actual_revenue", actual, "SUM(actual_revenue)", "KRW"),
                _metric("target_revenue", target, "SUM(target_revenue)", "KRW"),
                _metric(
                    "target_achievement_rate",
                    target_achievement(actual, target),
                    "actual_revenue / target_revenue * 100",
                    "%",
                ),
                _metric("target_gap", actual - target, "actual_revenue - target_revenue", "KRW"),
            ]
        )
        return metrics

    if {"category", "period", "revenue"} <= columns:
        pivot = frame.pivot_table(index="category", columns="period", values="revenue", aggfunc="sum", fill_value=0)
        for category, row in pivot.iterrows():
            current = float(row.get("current", 0))
            previous = float(row.get("previous", 0))
            metrics.append(
                _metric(
                    f"category_growth:{category}",
                    period_growth(current, previous),
                    "(current - previous) / previous * 100",
                    "%",
                    category=category,
                    current=current,
                    previous=previous,
                )
            )
        current_rows = frame[frame["period"] == "current"]
        if not current_rows.empty:
            winner = current_rows.loc[current_rows["revenue"].astype(float).idxmax()]
            metrics.append(
                _metric(
                    "top_current_category",
                    str(winner["category"]),
                    "ARGMAX(current revenue)",
                    category=str(winner["category"]),
                    revenue=float(winner["revenue"]),
                )
            )
        return metrics

    if {"device", "signup_users", "activated_users", "activation_rate"} <= columns:
        for _, row in frame.iterrows():
            metrics.append(
                _metric(
                    f"activation_rate:{row['device']}",
                    float(row["activation_rate"]),
                    "activated_users / signup_users * 100",
                    "%",
                    device=str(row["device"]),
                    signup_users=int(row["signup_users"]),
                    activated_users=int(row["activated_users"]),
                )
            )
        return metrics

    numeric = frame.select_dtypes(include="number")
    for column in numeric.columns:
        metrics.append(_metric(f"total:{column}", float(numeric[column].sum()), f"SUM({column})"))
    return metrics
