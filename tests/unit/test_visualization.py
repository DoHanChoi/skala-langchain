from __future__ import annotations

import pandas as pd
import pytest

from rolelens.domain.models import AnalysisPlan, ChartSpec, ChartType
from rolelens.visualization.chart_planner import InvalidChartSpec, plan_chart, validate_chart_spec
from rolelens.visualization.renderer import _prepared_frame, render_chart, try_render_chart


def _plan() -> AnalysisPlan:
    return AnalysisPlan(
        persona="planner",
        interpreted_question="매출 비교",
        metric="revenue",
        dimensions=["month"],
        filters=[],
        date_range="quarter",
        comparison="target",
        chart_hint=ChartType.GROUPED_BAR,
    )


def test_standard_revenue_chart_is_grouped_bar() -> None:
    frame = pd.DataFrame(
        {"month": ["2026-07"], "actual_revenue": [95.0], "target_revenue": [100.0]}
    )
    spec = plan_chart(_plan(), frame)
    assert spec.chart_type == ChartType.GROUPED_BAR
    assert render_chart(frame, spec) is not None


def test_missing_column_is_rejected() -> None:
    frame = pd.DataFrame({"x": ["a"], "y": [1]})
    spec = ChartSpec(chart_type="bar", x="missing", y="y", title="bad")
    with pytest.raises(InvalidChartSpec):
        validate_chart_spec(spec, frame)


def test_top_n_contract_is_at_most_ten() -> None:
    with pytest.raises(ValueError):
        ChartSpec(chart_type="bar", x="x", y="y", title="bad", top_n=11)


def test_top_n_keeps_all_series_rows_for_selected_categories() -> None:
    frame = pd.DataFrame(
        {
            "category": [f"c{i}" for i in range(12) for _ in ("current", "previous")],
            "period": [period for _ in range(12) for period in ("current", "previous")],
            "revenue": [float(i) for i in range(12) for _ in range(2)],
        }
    )
    spec = ChartSpec(
        chart_type="grouped_bar",
        x="category",
        y="revenue",
        series="period",
        title="top categories",
        top_n=10,
    )
    prepared = _prepared_frame(frame, spec)
    assert prepared["category"].nunique() == 10
    assert len(prepared) == 20


def test_renderer_failure_returns_dataframe_fallback_message(monkeypatch) -> None:  # noqa: ANN001
    frame = pd.DataFrame({"x": ["a"], "y": [1]})
    spec = ChartSpec(chart_type="bar", x="x", y="y", title="fallback")

    def fail(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("render failed")

    monkeypatch.setattr("rolelens.visualization.renderer.render_chart", fail)
    figure, message = try_render_chart(frame, spec)
    assert figure is None
    assert "데이터 표만 표시" in (message or "")
