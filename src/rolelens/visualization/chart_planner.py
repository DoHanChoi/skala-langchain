"""Rule-based ChartSpec generation and dataframe-aware validation."""

from __future__ import annotations

import pandas as pd

from rolelens.domain.models import AnalysisPlan, ChartSpec, ChartType


class InvalidChartSpec(ValueError):
    pass


def plan_chart(plan: AnalysisPlan, frame: pd.DataFrame) -> ChartSpec:
    columns = set(frame.columns)
    if {"month", "actual_revenue", "target_revenue"} <= columns:
        spec = ChartSpec(
            chart_type=ChartType.GROUPED_BAR,
            x="month",
            y="actual_revenue",
            series="target_revenue",
            title="월별 실제 매출과 목표 비교",
            x_label="월",
            y_label="매출(KRW)",
        )
    elif {"category", "period", "revenue"} <= columns:
        spec = ChartSpec(
            chart_type=ChartType.GROUPED_BAR,
            x="category",
            y="revenue",
            series="period",
            title="20대 카테고리별 매출 기간 비교",
            x_label="카테고리",
            y_label="매출(KRW)",
            top_n=10,
        )
    elif {"device", "activation_rate"} <= columns:
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="device",
            y="activation_rate",
            title="기기별 7일 활성화율",
            x_label="기기",
            y_label="활성화율(%)",
            sort="descending",
        )
    elif {"month", "new_customers", "target_new_customers"} <= columns:
        spec = ChartSpec(
            chart_type=ChartType.GROUPED_BAR,
            x="month",
            y="new_customers",
            series="target_new_customers",
            title="월별 신규 고객과 목표 비교",
            x_label="월",
            y_label="신규 고객(명)",
        )
    elif {"month", "acquisition_channel", "new_customers"} <= columns:
        spec = ChartSpec(
            chart_type=ChartType.STACKED_BAR,
            x="month",
            y="new_customers",
            series="acquisition_channel",
            title="유입 채널별 월 신규 고객",
            x_label="월",
            y_label="신규 고객(명)",
        )
    else:
        numeric = list(frame.select_dtypes(include="number").columns)
        non_numeric = [column for column in frame.columns if column not in numeric]
        if len(frame) == 1 and numeric:
            spec = ChartSpec(
                chart_type=ChartType.KPI,
                y=numeric[0],
                title=plan.interpreted_question,
            )
        elif numeric and non_numeric:
            spec = ChartSpec(
                chart_type=ChartType.BAR,
                x=non_numeric[0],
                y=numeric[0],
                title=plan.interpreted_question,
                top_n=10,
            )
        else:
            raise InvalidChartSpec("결과 컬럼으로 안전한 차트를 구성할 수 없습니다.")
    validate_chart_spec(spec, frame)
    return spec


def validate_chart_spec(spec: ChartSpec, frame: pd.DataFrame) -> None:
    for field_name in ("x", "y", "series"):
        column = getattr(spec, field_name)
        if column is not None and column not in frame.columns:
            raise InvalidChartSpec(f"{field_name} 컬럼이 결과에 없습니다: {column}")
    if spec.y and not pd.api.types.is_numeric_dtype(frame[spec.y]):
        raise InvalidChartSpec(f"y 컬럼은 수치여야 합니다: {spec.y}")
    if spec.chart_type == ChartType.SCATTER:
        if not spec.x or not pd.api.types.is_numeric_dtype(frame[spec.x]):
            raise InvalidChartSpec("scatter의 x, y는 수치여야 합니다.")
