from __future__ import annotations

from datetime import date

from langchain_core.runnables import RunnableLambda

from rolelens.agents.planner import LLMAnalysisPlanner
from rolelens.agents.sql_agent import LLMSQLAgent, SQLDraft, _result_contract_error
from rolelens.db.safety import validate_sql
from rolelens.domain.models import AnalysisPlan, AnalysisRequest, ChartType, QueryArtifact


class StructuredPlanModel:
    def __init__(self) -> None:
        self.calls = 0

    def with_structured_output(self, schema):  # noqa: ANN001, ANN201
        assert schema is AnalysisPlan

        def invoke(prompt_value):  # noqa: ANN001, ANN202
            self.calls += 1
            text = prompt_value.to_string()
            persona = next(name for name in ("planner", "marketer", "pm") if name in text)
            return AnalysisPlan(
                persona=persona,
                interpreted_question="stub",
                metric="revenue",
                dimensions=["month"],
                filters=["status = completed"],
                date_range="quarter",
                comparison="target",
                chart_hint=ChartType.GROUPED_BAR,
            )

        return RunnableLambda(invoke)


def test_llm_planner_uses_structured_output_behind_runnable_branch() -> None:
    planner = LLMAnalysisPlanner(StructuredPlanModel())
    plan = planner.plan(
        AnalysisRequest(persona="marketer", question="지난 분기 매출을 분석해줘")
    )
    assert isinstance(plan, AnalysisPlan)
    assert plan.persona == "marketer"


def test_llm_planner_short_circuits_documented_ambiguous_question() -> None:
    model = StructuredPlanModel()
    plan = LLMAnalysisPlanner(model).plan(
        AnalysisRequest(persona="marketer", question="요즘 잘 나가는 상품을 보여줘.")
    )
    assert plan.clarification_needed is True
    assert plan.clarification_question
    assert model.calls == 0


class UnderspecifiedNewCustomerModel:
    def with_structured_output(self, schema):  # noqa: ANN001, ANN201
        assert schema is AnalysisPlan
        return RunnableLambda(
            lambda _prompt: AnalysisPlan(
                persona="planner",
                interpreted_question="recent new customer change",
                metric="new_customers",
                dimensions=["date"],
                filters=["first completed order"],
                date_range="latest six months",
                comparison="previous period",
                chart_hint=ChartType.KPI,
            )
        )


def test_llm_planner_applies_persona_defaults_when_model_omits_focus() -> None:
    planner = LLMAnalysisPlanner(UnderspecifiedNewCustomerModel())
    plans = {
        persona: planner.plan(
            AnalysisRequest(persona=persona, question="최근 신규 고객 수가 어떻게 변했어?")
        )
        for persona in ("planner", "marketer", "pm")
    }

    assert {plan.persona for plan in plans.values()} == {"planner", "marketer", "pm"}
    assert {plan.metric for plan in plans.values()} == {"new_customers"}
    assert len({tuple(plan.dimensions) for plan in plans.values()}) == 3
    assert len({plan.comparison for plan in plans.values()}) == 3


def test_llm_planner_prioritizes_explicit_new_customer_dimension() -> None:
    plan = LLMAnalysisPlanner(UnderspecifiedNewCustomerModel()).plan(
        AnalysisRequest(
            persona="marketer",
            question="최근 신규 고객 수를 지역별로 보여줘.",
        )
    )
    assert plan.dimensions == ["region"]


class WrongStandardPlanModel:
    def with_structured_output(self, schema):  # noqa: ANN001, ANN201
        assert schema is AnalysisPlan
        return RunnableLambda(
            lambda _prompt: AnalysisPlan(
                persona="planner",
                interpreted_question="generic",
                metric="revenue",
                dimensions=["date"],
                filters=[],
                date_range="recent",
                comparison=None,
                chart_hint=ChartType.BAR,
            )
        )


def test_explicit_standard_questions_normalize_result_contracts() -> None:
    planner = LLMAnalysisPlanner(WrongStandardPlanModel())
    marketer = planner.plan(
        AnalysisRequest(
            persona="marketer",
            question="최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.",
        )
    )
    pm = planner.plan(
        AnalysisRequest(
            persona="pm",
            question="최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.",
        )
    )
    assert marketer.dimensions == ["category", "period"]
    assert marketer.filters == ["20 <= age < 30", "status = completed"]
    assert marketer.chart_hint == ChartType.GROUPED_BAR
    assert pm.metric == "activation_rate_7d"
    assert pm.dimensions == ["device"]
    assert pm.chart_hint == ChartType.BAR


def test_standard_result_contracts_reject_wrong_shapes() -> None:
    marketer_plan = AnalysisPlan(
        persona="marketer",
        interpreted_question="category comparison",
        metric="revenue",
        dimensions=["category", "period"],
        filters=["20 <= age < 30"],
        date_range="six months",
        comparison="previous_3_months",
        chart_hint=ChartType.GROUPED_BAR,
    )
    wrong = QueryArtifact(
        sql="SELECT order_id FROM analytics.orders LIMIT 1",
        columns=["order_id"],
        rows=[{"order_id": 1}],
        source_tables=["orders"],
        row_count=1,
        data_as_of=date(2026, 9, 15),
        attempts=1,
    )
    assert _result_contract_error(marketer_plan, wrong)

    pm_plan = marketer_plan.model_copy(
        update={
            "persona": "pm",
            "metric": "activation_rate_7d",
            "dimensions": ["device"],
            "comparison": "device",
            "chart_hint": ChartType.BAR,
        }
    )
    assert _result_contract_error(pm_plan, wrong)


def test_standard_result_contract_rejects_empty_or_one_sided_periods() -> None:
    plan = AnalysisPlan(
        persona="marketer",
        interpreted_question="category comparison",
        metric="revenue",
        dimensions=["category", "period"],
        filters=["20 <= age < 30"],
        date_range="six months",
        comparison="previous_3_months",
        chart_hint=ChartType.GROUPED_BAR,
    )
    empty = QueryArtifact(
        sql="SELECT category, 'current' AS period, list_price AS revenue FROM analytics.products WHERE FALSE LIMIT 100",
        columns=["category", "period", "revenue"],
        rows=[],
        source_tables=["products"],
        row_count=0,
        data_as_of=date(2026, 9, 15),
        attempts=1,
    )
    current_only = empty.model_copy(
        update={
            "rows": [{"category": "beauty", "period": "current", "revenue": 1}],
            "row_count": 1,
        }
    )
    assert _result_contract_error(plan, empty)
    assert _result_contract_error(plan, current_only)


class RepairModel:
    def __init__(self) -> None:
        self.calls = 0

    def with_structured_output(self, schema):  # noqa: ANN001, ANN201
        assert schema is SQLDraft

        def invoke(_prompt_value):  # noqa: ANN001, ANN202
            self.calls += 1
            if self.calls == 1:
                return SQLDraft(sql="SELECT * FROM analytics.orders")
            return SQLDraft(sql="SELECT order_id FROM analytics.orders ORDER BY order_id LIMIT 1")

        return RunnableLambda(invoke)


class FakeRepository:
    def list_tables(self):  # noqa: ANN201
        return [{"name": "orders", "description": "orders"}]

    def inspect_schema(self, table_names):  # noqa: ANN001, ANN201
        return [{"name": "orders", "columns": [{"name": "order_id", "type": "BIGINT"}]}]

    def execute_readonly_sql(self, sql: str, attempts: int = 1) -> QueryArtifact:
        validated = validate_sql(sql)
        return QueryArtifact(
            sql=validated.sql,
            columns=["order_id"],
            rows=[{"order_id": 1}],
            source_tables=["orders"],
            row_count=1,
            data_as_of=date(2026, 9, 15),
            attempts=attempts,
        )


def test_sql_agent_repairs_invalid_sql_within_bound() -> None:
    model = RepairModel()
    agent = LLMSQLAgent(model, FakeRepository(), validate_reference_sql=False)
    plan = AnalysisPlan(
        persona="planner",
        interpreted_question="orders",
        metric="orders",
        dimensions=[],
        filters=[],
        date_range="all",
        comparison=None,
        chart_hint=ChartType.KPI,
    )
    artifact = agent.run(plan)
    assert artifact.attempts == 2
    assert model.calls == 2


class ResultContractRepairModel:
    def __init__(self) -> None:
        self.calls = 0

    def with_structured_output(self, schema):  # noqa: ANN001, ANN201
        assert schema is SQLDraft

        def invoke(_prompt_value):  # noqa: ANN001, ANN202
            self.calls += 1
            if self.calls == 1:
                return SQLDraft(sql="SELECT order_id FROM analytics.orders LIMIT 1")
            return SQLDraft(
                sql=(
                    "SELECT order_id AS month, order_id AS actual_revenue, "
                    "order_id AS target_revenue, order_id AS achievement_rate "
                    "FROM analytics.orders LIMIT 1"
                )
            )

        return RunnableLambda(invoke)


class ResultContractRepository(FakeRepository):
    def execute_readonly_sql(self, sql: str, attempts: int = 1) -> QueryArtifact:
        validated = validate_sql(sql)
        if "achievement_rate" not in validated.sql:
            columns = ["order_id"]
            rows = [{"order_id": 1}]
        else:
            columns = ["month", "actual_revenue", "target_revenue", "achievement_rate"]
            rows = [
                {
                    "month": "2026-07-01",
                    "actual_revenue": 95,
                    "target_revenue": 100,
                    "achievement_rate": 95,
                }
            ]
        return QueryArtifact(
            sql=validated.sql,
            columns=columns,
            rows=rows,
            source_tables=["orders"],
            row_count=1,
            data_as_of=date(2026, 9, 15),
            attempts=attempts,
        )


def test_sql_agent_repairs_executable_but_wrong_result_contract() -> None:
    model = ResultContractRepairModel()
    agent = LLMSQLAgent(
        model, ResultContractRepository(), validate_reference_sql=False
    )
    plan = AnalysisPlan(
        persona="planner",
        interpreted_question="monthly revenue versus target",
        metric="revenue",
        dimensions=["month"],
        filters=["status = completed"],
        date_range="quarter",
        comparison="target",
        chart_hint=ChartType.GROUPED_BAR,
    )

    artifact = agent.run(plan)

    assert artifact.attempts == 2
    assert model.calls == 2
    assert set(artifact.columns) >= {
        "month",
        "actual_revenue",
        "target_revenue",
        "achievement_rate",
    }
