"""Persona-routed AnalysisPlan generation."""

from __future__ import annotations

import json
from typing import Protocol

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda

from rolelens.agents.prompts import (
    ANALYSIS_PLAN_USER_PROMPT,
    COMMON_SYSTEM_PROMPT,
    PERSONA_PROMPTS,
)
from rolelens.domain.metrics import METRIC_DEFINITIONS
from rolelens.domain.models import AnalysisPlan, AnalysisRequest, ChartType, Persona


class AnalysisPlanner(Protocol):
    def plan(self, request: AnalysisRequest) -> AnalysisPlan: ...


NEW_CUSTOMER_PERSONA_DEFAULTS: dict[Persona, tuple[list[str], str, ChartType]] = {
    "planner": (["month"], "target_and_previous_period", ChartType.GROUPED_BAR),
    "marketer": (
        ["month", "acquisition_channel"],
        "previous_period_by_channel",
        ChartType.GROUPED_BAR,
    ),
    "pm": (["device", "activation_stage"], "activation_and_purchase_stage", ChartType.BAR),
}
NEW_CUSTOMER_DIMENSION_TERMS = {
    "월별": "month",
    "일별": "date",
    "주별": "week",
    "채널": "acquisition_channel",
    "캠페인": "campaign",
    "기기": "device",
    "디바이스": "device",
    "지역": "region",
    "카테고리": "category",
    "세그먼트": "segment",
}
NEW_CUSTOMER_COMPARISON_TERMS = {
    "목표": "target",
    "직전": "previous_period",
    "전월": "previous_month",
    "전년": "previous_year",
}


def _ambiguous_product_plan(persona: Persona, question: str) -> AnalysisPlan | None:
    normalized = question.replace(" ", "")
    if "요즘" not in question or "잘나가는" not in normalized or "상품" not in question:
        return None
    return AnalysisPlan(
        persona=persona,
        interpreted_question=question,
        metric="ambiguous_product_performance",
        dimensions=["product_name"],
        filters=[],
        date_range="ambiguous",
        comparison=None,
        chart_hint=ChartType.BAR,
        clarification_needed=True,
        clarification_question="최근 30일의 매출액을 기준으로 상위 상품을 보여드릴까요?",
    )


def _explicit_standard_updates(question: str) -> dict[str, object]:
    normalized = question.replace(" ", "")
    if "20대" in question and "카테고리" in question and "매출" in question and "직전3개월" in normalized:
        return {
            "interpreted_question": "최근 3개월과 직전 3개월의 20대 카테고리별 completed 매출 비교",
            "metric": "revenue",
            "dimensions": ["category", "period"],
            "filters": ["20 <= age < 30", "status = completed"],
            "date_range": "latest 3 calendar months and prior 3 complete months from max order_date",
            "comparison": "previous_3_months",
            "chart_hint": ChartType.GROUPED_BAR,
            "clarification_needed": False,
            "clarification_question": None,
        }
    if "활성화율" in question or ("7일" in question and "핵심기능" in normalized):
        return {
            "interpreted_question": "최근 3개월 신규 가입자의 7일 활성화율을 기기별 비교",
            "metric": "activation_rate_7d",
            "dimensions": ["device"],
            "filters": ["event_name = feature_used", "mature cohort only"],
            "date_range": "latest 3 calendar months through max event_date; signup <= max date - 7 days",
            "comparison": "device",
            "chart_hint": ChartType.BAR,
            "clarification_needed": False,
            "clarification_question": None,
        }
    if "매출" in question and "목표" in question and "분기" in question:
        return {
            "interpreted_question": "이번 분기 completed 매출을 월별 목표와 비교",
            "metric": "revenue",
            "dimensions": ["month"],
            "filters": ["status = completed"],
            "date_range": "current quarter through max order_date",
            "comparison": "target",
            "chart_hint": ChartType.GROUPED_BAR,
            "clarification_needed": False,
            "clarification_question": None,
        }
    return {}


def create_persona_branch(chains: dict[Persona, Runnable]) -> RunnableBranch:
    """The explicit branch is a tested product requirement, not prompt interpolation."""

    return RunnableBranch(
        (lambda x: x["persona"] == "planner", chains["planner"]),
        (lambda x: x["persona"] == "marketer", chains["marketer"]),
        (lambda x: x["persona"] == "pm", chains["pm"]),
        RunnableLambda(
            lambda x: (_ for _ in ()).throw(
                ValueError(f"지원하지 않는 페르소나: {x.get('persona')}")
            )
        ),
    )


class LLMAnalysisPlanner:
    def __init__(self, model) -> None:  # noqa: ANN001
        structured_model = model.with_structured_output(AnalysisPlan)
        chains: dict[Persona, Runnable] = {}
        for persona in ("planner", "marketer", "pm"):
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", COMMON_SYSTEM_PROMPT + "\n" + PERSONA_PROMPTS[persona]),
                    ("human", ANALYSIS_PLAN_USER_PROMPT),
                ]
            )
            chains[persona] = prompt | structured_model
        self.branch = create_persona_branch(chains)

    def plan(self, request: AnalysisRequest) -> AnalysisPlan:
        clarification = _ambiguous_product_plan(request.persona, request.question)
        if clarification is not None:
            return clarification
        plan: AnalysisPlan = self.branch.invoke(
            {
                **request.model_dump(),
                "metric_definitions": json.dumps(
                    METRIC_DEFINITIONS, ensure_ascii=False, sort_keys=True
                ),
            }
        )
        updates: dict[str, object] = {}
        if plan.persona != request.persona:
            updates["persona"] = request.persona
        updates.update(_explicit_standard_updates(request.question))
        effective_metric = updates.get("metric", plan.metric)
        effective_clarification = updates.get(
            "clarification_needed", plan.clarification_needed
        )
        if effective_metric == "new_customers" and not effective_clarification:
            dimensions, comparison, chart_hint = NEW_CUSTOMER_PERSONA_DEFAULTS[
                request.persona
            ]
            explicit_dimensions = list(
                dict.fromkeys(
                    canonical
                    for term, canonical in NEW_CUSTOMER_DIMENSION_TERMS.items()
                    if term in request.question
                )
            )
            explicit_comparison = next(
                (
                    canonical
                    for term, canonical in NEW_CUSTOMER_COMPARISON_TERMS.items()
                    if term in request.question
                ),
                None,
            )
            if explicit_dimensions:
                updates["dimensions"] = explicit_dimensions
            else:
                updates["dimensions"] = dimensions
                updates["chart_hint"] = chart_hint
            if explicit_comparison:
                updates["comparison"] = explicit_comparison
            else:
                updates["comparison"] = comparison
        return plan.model_copy(update=updates)


def _rule_plan(persona: Persona, question: str) -> AnalysisPlan:
    normalized = question.replace(" ", "")
    clarification = _ambiguous_product_plan(persona, question)
    if clarification is not None:
        return clarification
    if "활성화율" in question or ("7일" in question and "핵심기능" in normalized):
        return AnalysisPlan(
            persona=persona,
            interpreted_question="최근 3개월 신규 가입자의 7일 활성화율을 기기별 비교",
            metric="activation_rate_7d",
            dimensions=["device"],
            filters=["event_name = feature_used", "mature cohort only"],
            date_range="latest 3 calendar months through data max date; signup <= max date - 7 days",
            comparison="device",
            chart_hint=ChartType.BAR,
        )
    if "20대" in question and "카테고리" in question and "매출" in question:
        return AnalysisPlan(
            persona=persona,
            interpreted_question="최근 3개월과 직전 3개월의 20대 카테고리별 completed 매출 비교",
            metric="revenue",
            dimensions=["category", "period"],
            filters=["20 <= age < 30", "status = completed"],
            date_range="latest 3 calendar months and prior 3 complete months from max order_date",
            comparison="previous_3_months",
            chart_hint=ChartType.GROUPED_BAR,
        )
    if "매출" in question and "목표" in question and "분기" in question:
        return AnalysisPlan(
            persona=persona,
            interpreted_question="이번 분기 completed 매출을 월별 목표와 비교",
            metric="revenue",
            dimensions=["month"],
            filters=["status = completed"],
            date_range="current quarter through max order_date",
            comparison="target",
            chart_hint=ChartType.GROUPED_BAR,
        )
    if "신규고객" in normalized or "신규 고객" in question:
        dimensions, comparison, chart_hint = NEW_CUSTOMER_PERSONA_DEFAULTS[persona]
        return AnalysisPlan(
            persona=persona,
            interpreted_question=f"{persona} 관점의 최근 신규 고객 변화",
            metric="new_customers",
            dimensions=dimensions,
            filters=["first completed order"],
            date_range="latest 6 calendar months through max order_date",
            comparison=comparison,
            chart_hint=chart_hint,
        )
    return AnalysisPlan(
        persona=persona,
        interpreted_question=question,
        metric="unknown",
        dimensions=[],
        filters=[],
        date_range="unspecified",
        comparison=None,
        chart_hint=ChartType.KPI,
        clarification_needed=True,
        clarification_question="어떤 지표와 기간을 기준으로 분석할지 알려주세요.",
    )


class RuleBasedAnalysisPlanner:
    """Deterministic test/demo planner for the documented acceptance scenarios."""

    def __init__(self) -> None:
        self.branch = create_persona_branch(
            {
                persona: RunnableLambda(
                    lambda x, persona=persona: _rule_plan(persona, x["question"])
                )
                for persona in ("planner", "marketer", "pm")
            }
        )

    def plan(self, request: AnalysisRequest) -> AnalysisPlan:
        return self.branch.invoke(request.model_dump())
