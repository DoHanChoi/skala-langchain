from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolelens.domain.models import AnalysisPlan, AnalysisRequest, ChartSpec, ChartType


def test_analysis_request_trims_question() -> None:
    request = AnalysisRequest(persona="planner", question="  매출은?  ")
    assert request.question == "매출은?"


@pytest.mark.parametrize("question", ["", " ", "\n\t"])
def test_analysis_request_rejects_blank(question: str) -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(persona="planner", question=question)


def test_analysis_request_rejects_unknown_persona() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(persona="analyst", question="매출은?")


def test_clarification_requires_question() -> None:
    with pytest.raises(ValidationError):
        AnalysisPlan(
            persona="planner",
            interpreted_question="x",
            metric="x",
            dimensions=[],
            filters=[],
            date_range="x",
            chart_hint=ChartType.KPI,
            clarification_needed=True,
        )


def test_grouped_bar_requires_series() -> None:
    with pytest.raises(ValidationError):
        ChartSpec(chart_type="grouped_bar", x="x", y="y", title="x")
