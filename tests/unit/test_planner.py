from __future__ import annotations

from rolelens.agents.planner import RuleBasedAnalysisPlanner
from rolelens.domain.models import AnalysisRequest


def test_persona_branch_changes_common_question_focus() -> None:
    planner = RuleBasedAnalysisPlanner()
    plans = {
        persona: planner.plan(
            AnalysisRequest(persona=persona, question="최근 신규 고객 수가 어떻게 변했어?")
        )
        for persona in ("planner", "marketer", "pm")
    }
    assert plans["planner"].dimensions == ["month"]
    assert "acquisition_channel" in plans["marketer"].dimensions
    assert "activation_stage" in plans["pm"].dimensions
    assert {plan.metric for plan in plans.values()} == {"new_customers"}
    assert len({plan.comparison for plan in plans.values()}) == 3


def test_ambiguous_question_stops_before_sql() -> None:
    plan = RuleBasedAnalysisPlanner().plan(
        AnalysisRequest(persona="marketer", question="요즘 잘 나가는 상품을 보여줘.")
    )
    assert plan.clarification_needed is True
    assert plan.clarification_question
