"""Safe matplotlib renderer. No model-generated Python is executed."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from rolelens.domain.models import ChartSpec, ChartType
from rolelens.visualization.chart_planner import validate_chart_spec


def _configure_korean_font() -> None:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in ("AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Malgun Gothic"):
        if candidate in available:
            plt.rcParams["font.family"] = candidate
            plt.rcParams["axes.unicode_minus"] = False
            return


def _prepared_frame(frame: pd.DataFrame, spec: ChartSpec) -> pd.DataFrame:
    result = frame.copy()
    if spec.x and pd.api.types.is_datetime64_any_dtype(result[spec.x]):
        result[spec.x] = result[spec.x].dt.strftime("%Y-%m-%d")
    if spec.x:
        result[spec.x] = result[spec.x].astype(str)
    if spec.sort != "none" and spec.y:
        result = result.sort_values(spec.y, ascending=spec.sort == "ascending")
    if spec.top_n and spec.x and spec.y:
        top_categories = (
            result.groupby(spec.x, dropna=False)[spec.y]
            .sum()
            .nlargest(spec.top_n)
            .index
        )
        result = result[result[spec.x].isin(top_categories)]
    return result


def render_chart(frame: pd.DataFrame, spec: ChartSpec) -> Figure:
    _configure_korean_font()
    validate_chart_spec(spec, frame)
    data = _prepared_frame(frame, spec)
    fig, ax = plt.subplots(figsize=(9, 4.8))

    if spec.chart_type == ChartType.KPI:
        value = data[spec.y].iloc[0]
        ax.text(0.5, 0.5, f"{value:,.2f}" if isinstance(value, float) else str(value), ha="center", va="center", fontsize=28)
        ax.axis("off")
    elif spec.chart_type in {ChartType.GROUPED_BAR, ChartType.STACKED_BAR}:
        if pd.api.types.is_numeric_dtype(data[spec.series]):
            data.plot(
                x=spec.x,
                y=[spec.y, spec.series],
                kind="bar",
                stacked=spec.chart_type == ChartType.STACKED_BAR,
                ax=ax,
            )
        else:
            pivot = data.pivot_table(
                index=spec.x, columns=spec.series, values=spec.y, aggfunc="sum", fill_value=0
            )
            pivot.plot(
                kind="bar", stacked=spec.chart_type == ChartType.STACKED_BAR, ax=ax
            )
    elif spec.chart_type == ChartType.HORIZONTAL_BAR:
        data.plot(x=spec.x, y=spec.y, kind="barh", legend=False, ax=ax)
    elif spec.chart_type == ChartType.LINE:
        data.plot(x=spec.x, y=spec.y, kind="line", marker="o", legend=False, ax=ax)
    elif spec.chart_type == ChartType.SCATTER:
        data.plot(x=spec.x, y=spec.y, kind="scatter", legend=False, ax=ax)
    else:
        data.plot(x=spec.x, y=spec.y, kind="bar", legend=False, ax=ax)

    ax.set_title(spec.title)
    if spec.x_label:
        ax.set_xlabel(spec.x_label)
    if spec.y_label:
        ax.set_ylabel(spec.y_label)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    return fig


def try_render_chart(frame: pd.DataFrame, spec: ChartSpec) -> tuple[Figure | None, str | None]:
    try:
        return render_chart(frame, spec), None
    except Exception as exc:  # renderer failures must not terminate the UI process
        return None, f"차트를 생성할 수 없어 데이터 표만 표시합니다: {exc}"
