"""Evidence-only Insight Card writers with deterministic fallback."""

from __future__ import annotations

import json
import re
from typing import Protocol

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from rolelens.agents.prompts import COMMON_SYSTEM_PROMPT, INSIGHT_WRITER_PROMPT
from rolelens.domain.metrics import METRIC_DEFINITIONS
from rolelens.domain.models import (
    AnalysisPlan,
    AnalysisRequest,
    ChartSpec,
    ComputedMetric,
    InsightCard,
    QueryArtifact,
)


class EvidenceNarrative(BaseModel):
    headline: str
    key_findings: list[str] = Field(min_length=2, max_length=3)
    applied_context: list[str]
    next_analysis_question: str
    caveats: list[str] = Field(default_factory=list, max_length=2)


class InsightWriter(Protocol):
    def write(
        self,
        request: AnalysisRequest,
        plan: AnalysisPlan,
        query: QueryArtifact,
        metrics: list[ComputedMetric],
        chart_spec: ChartSpec,
    ) -> InsightCard: ...


def _krw(value: float) -> str:
    return f"{value:,.0f}원"


def _percent(value: float | int | None) -> str:
    return "계산 불가" if value is None else f"{float(value):,.2f}%"


def _by_name(metrics: list[ComputedMetric]) -> dict[str, ComputedMetric]:
    return {item.name: item for item in metrics}


class DeterministicInsightWriter:
    def _narrative(
        self, request: AnalysisRequest, plan: AnalysisPlan, query: QueryArtifact, metrics: list[ComputedMetric]
    ) -> EvidenceNarrative:
        named = _by_name(metrics)
        if "target_achievement_rate" in named:
            actual = float(named["actual_revenue"].value or 0)
            target = float(named["target_revenue"].value or 0)
            rate = named["target_achievement_rate"].value
            gap = float(named["target_gap"].value or 0)
            achievement_state = "목표를 달성했습니다" if rate is not None and float(rate) >= 100 else "목표에 미달했습니다"
            return EvidenceNarrative(
                headline=f"이번 분기 매출 목표 달성률은 {_percent(rate)}로 {achievement_state}.",
                key_findings=[
                    f"완료 주문 매출은 {_krw(actual)}, 목표는 {_krw(target)}입니다.",
                    f"목표 대비 격차는 {_krw(gap)}입니다.",
                ],
                applied_context=[plan.date_range, "completed 주문만 매출에 포함", METRIC_DEFINITIONS["revenue"]],
                next_analysis_question="목표 격차가 큰 카테고리와 지역을 나눠서 보시겠어요?",
                caveats=["2026년 9월은 데이터 기준일까지의 누적값입니다."],
            )
        growth_metrics = [m for m in metrics if m.name.startswith("category_growth:")]
        if growth_metrics:
            top = named.get("top_current_category")
            valid_growth = [m for m in growth_metrics if isinstance(m.value, (int, float))]
            fastest = max(valid_growth, key=lambda item: float(item.value))
            category = str(top.value) if top else "확인 불가"
            revenue = float(top.context.get("revenue", 0)) if top else 0
            return EvidenceNarrative(
                headline=f"최근 3개월 20대 매출은 {category} 카테고리가 {_krw(revenue)}으로 가장 큽니다.",
                key_findings=[
                    f"현재 기간 매출 1위 카테고리는 {category}입니다.",
                    f"직전 기간 대비 증가율은 {fastest.context['category']}가 {_percent(fastest.value)}로 가장 큽니다.",
                ],
                applied_context=[plan.date_range, "20 <= age < 30", METRIC_DEFINITIONS["revenue"]],
                next_analysis_question=f"{category} 매출 증가가 특정 채널이나 캠페인에 집중됐는지 보시겠어요?",
                caveats=["Mock 데이터의 관찰 차이며 인과를 의미하지 않습니다."],
            )
        activation = [m for m in metrics if m.name.startswith("activation_rate:")]
        if activation:
            ordered = sorted(activation, key=lambda item: float(item.value or 0), reverse=True)
            high, low = ordered[0], ordered[-1]
            return EvidenceNarrative(
                headline=f"7일 활성화율은 {high.context['device']}가 {_percent(high.value)}로 가장 높습니다.",
                key_findings=[
                    f"{high.context['device']}는 {high.context['signup_users']}명 중 {high.context['activated_users']}명이 활성화했습니다.",
                    f"{low.context['device']}는 {low.context['signup_users']}명 중 {low.context['activated_users']}명으로 활성화율이 {_percent(low.value)}입니다.",
                ],
                applied_context=[plan.date_range, "feature_used within signup+7 days", METRIC_DEFINITIONS["activation_rate_7d"]],
                next_analysis_question=f"{low.context['device']} 가입자의 7일 내 행동 단계별 이탈을 비교해 보시겠어요?",
                caveats=["가입 후 7일 관찰 기간이 완성된 cohort만 포함했습니다."],
            )

        row_count = query.row_count
        numeric_metrics = [m for m in metrics if isinstance(m.value, (int, float))]
        first = numeric_metrics[0] if numeric_metrics else None
        value_text = f"{first.value:,.2f}" if first and isinstance(first.value, float) else str(first.value if first else row_count)
        return EvidenceNarrative(
            headline=f"요청한 조건에서 {row_count}개 결과 행을 확인했습니다.",
            key_findings=[
                f"첫 수치 지표 값은 {value_text}입니다.",
                f"데이터 기준일은 {query.data_as_of.isoformat()}입니다.",
            ],
            applied_context=[plan.date_range, *plan.filters],
            next_analysis_question="결과를 어떤 하위 세그먼트로 나눠서 보시겠어요?",
            caveats=["Mock 데이터 기반 결과입니다."],
        )

    def write(
        self,
        request: AnalysisRequest,
        plan: AnalysisPlan,
        query: QueryArtifact,
        metrics: list[ComputedMetric],
        chart_spec: ChartSpec,
    ) -> InsightCard:
        narrative = self._narrative(request, plan, query, metrics)
        return InsightCard(
            persona=request.persona,
            question=request.question,
            chart_spec=chart_spec,
            sql=query.sql,
            source_tables=query.source_tables,
            row_count=query.row_count,
            data_as_of=query.data_as_of,
            **narrative.model_dump(),
        )


def _numeric_tokens(text: str) -> set[str]:
    return {token.replace(",", "") for token in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)}


def _contains_unverified_causality(text: str) -> bool:
    return any(phrase in text for phrase in ("때문에", "원인은", "원인이다", "원인입니다"))


class LLMInsightWriter:
    """Uses structured output, then rejects unsupported numbers and falls back safely."""

    def __init__(self, model, fallback: InsightWriter | None = None) -> None:  # noqa: ANN001
        prompt = ChatPromptTemplate.from_messages(
            [("system", COMMON_SYSTEM_PROMPT), ("human", INSIGHT_WRITER_PROMPT)]
        )
        self.chain = prompt | model.with_structured_output(EvidenceNarrative)
        self.fallback = fallback or DeterministicInsightWriter()

    def write(
        self,
        request: AnalysisRequest,
        plan: AnalysisPlan,
        query: QueryArtifact,
        metrics: list[ComputedMetric],
        chart_spec: ChartSpec,
    ) -> InsightCard:
        evidence = json.dumps(
            {
                "question": request.question,
                "plan": plan.model_dump(mode="json"),
                "rows": query.rows,
                "metrics": [m.model_dump() for m in metrics],
                "chart_spec": chart_spec.model_dump(mode="json"),
                "metric_definition": METRIC_DEFINITIONS.get(plan.metric, plan.metric),
            },
            ensure_ascii=False,
            default=str,
        )
        narrative: EvidenceNarrative = self.chain.invoke(
            {
                "question": request.question,
                "persona": request.persona,
                "analysis_plan": plan.model_dump_json(),
                "rows": json.dumps(query.rows[:20], ensure_ascii=False, default=str),
                "computed_metrics": json.dumps(
                    [m.model_dump() for m in metrics], ensure_ascii=False, default=str
                ),
                "chart_spec": chart_spec.model_dump_json(),
                "metric_definition": METRIC_DEFINITIONS.get(plan.metric, plan.metric),
            }
        )
        output_text = " ".join(
            [
                narrative.headline,
                *narrative.key_findings,
                *narrative.applied_context,
                narrative.next_analysis_question,
                *narrative.caveats,
            ]
        )
        if (
            not _numeric_tokens(output_text) <= _numeric_tokens(evidence)
            or _contains_unverified_causality(output_text)
        ):
            return self.fallback.write(request, plan, query, metrics, chart_spec)
        return InsightCard(
            persona=request.persona,
            question=request.question,
            chart_spec=chart_spec,
            sql=query.sql,
            source_tables=query.source_tables,
            row_count=query.row_count,
            data_as_of=query.data_as_of,
            **narrative.model_dump(),
        )
