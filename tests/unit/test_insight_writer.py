from __future__ import annotations

from datetime import date

import pandas as pd
from langchain_core.runnables import RunnableLambda

from rolelens.agents.insight_writer import EvidenceNarrative, LLMInsightWriter
from rolelens.domain.metrics import analyze_result
from rolelens.domain.models import (
    AnalysisPlan,
    AnalysisRequest,
    ChartSpec,
    ChartType,
    QueryArtifact,
)


class UnsupportedClaimModel:
    def with_structured_output(self, schema):  # noqa: ANN001, ANN201
        assert schema is EvidenceNarrative
        return RunnableLambda(
            lambda _prompt: EvidenceNarrative(
                headline="모델 헤드라인",
                key_findings=["실제 매출은 95입니다.", "목표는 100입니다."],
                applied_context=["이번 분기"],
                next_analysis_question="999개 세그먼트를 추가로 보시겠어요?",
                caveats=["목표 미달은 기기 문제 때문에 발생했습니다."],
            )
        )


def test_unsupported_number_or_causality_uses_deterministic_fallback() -> None:
    request = AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?")
    plan = AnalysisPlan(
        persona="planner",
        interpreted_question="분기 매출 목표 비교",
        metric="revenue",
        dimensions=["month"],
        filters=["status = completed"],
        date_range="current quarter",
        comparison="target",
        chart_hint=ChartType.GROUPED_BAR,
    )
    rows = [
        {
            "month": date(2026, 7, 1),
            "actual_revenue": 95.0,
            "target_revenue": 100.0,
            "achievement_rate": 95.0,
        }
    ]
    query = QueryArtifact(
        sql="SELECT target_month AS month FROM analytics.monthly_targets LIMIT 100",
        columns=list(rows[0]),
        rows=rows,
        source_tables=["monthly_targets"],
        row_count=1,
        data_as_of=date(2026, 9, 15),
        attempts=1,
    )
    metrics = analyze_result(pd.DataFrame(rows))
    spec = ChartSpec(
        chart_type=ChartType.GROUPED_BAR,
        x="month",
        y="actual_revenue",
        series="target_revenue",
        title="월별 실적과 목표",
    )

    insight = LLMInsightWriter(UnsupportedClaimModel()).write(
        request, plan, query, metrics, spec
    )

    assert insight.headline != "모델 헤드라인"
    assert "95.00%" in insight.headline
    assert "999" not in " ".join(
        [insight.headline, *insight.key_findings, insight.next_analysis_question]
    )
