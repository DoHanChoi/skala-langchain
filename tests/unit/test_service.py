from __future__ import annotations

from datetime import date

import pandas as pd

from rolelens.agents.insight_writer import DeterministicInsightWriter
from rolelens.agents.planner import RuleBasedAnalysisPlanner
from rolelens.db.repository import QueryExecutionError
from rolelens.domain.models import AnalysisRequest, QueryArtifact
from rolelens.services.insight_service import InsightService


class CountingSQLRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, plan):  # noqa: ANN001, ANN201
        self.calls += 1
        return QueryArtifact(
            sql="SELECT 1 AS value LIMIT 100",
            columns=["value"],
            rows=[{"value": 1}],
            source_tables=[],
            row_count=1,
            data_as_of=date(2026, 9, 15),
            attempts=1,
        )


def _target_artifact(rows: list[dict] | None = None) -> QueryArtifact:
    result_rows = rows if rows is not None else [
        {
            "month": date(2026, 7, 1),
            "actual_revenue": 95.0,
            "target_revenue": 100.0,
            "achievement_rate": 95.0,
        }
    ]
    return QueryArtifact(
        sql=(
            "SELECT target_month AS month, target_value AS actual_revenue, "
            "target_value AS target_revenue, 100 AS achievement_rate "
            "FROM analytics.monthly_targets LIMIT 100"
        ),
        columns=["month", "actual_revenue", "target_revenue", "achievement_rate"],
        rows=result_rows,
        source_tables=["monthly_targets"],
        row_count=len(result_rows),
        data_as_of=date(2026, 9, 15),
        attempts=1,
    )


class ArtifactRunner:
    def __init__(self, artifact: QueryArtifact):
        self.artifact = artifact

    def run(self, _plan):  # noqa: ANN001, ANN201
        return self.artifact


def test_clarification_does_not_call_sql() -> None:
    runner = CountingSQLRunner()
    service = InsightService(
        RuleBasedAnalysisPlanner(), runner, DeterministicInsightWriter()
    )
    response = service.run(
        AnalysisRequest(persona="marketer", question="요즘 잘 나가는 상품을 보여줘.")
    )
    assert response.status == "clarification"
    assert runner.calls == 0


def test_missing_credentials_is_safe_error(settings) -> None:  # noqa: ANN001
    from rolelens.services.insight_service import build_service

    response = build_service(settings).run(
        AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?")
    )
    assert response.status == "error"
    assert "API_KEY" in (response.user_message or "")
    assert "postgresql" not in (response.user_message or "").lower()


def test_trace_has_one_request_id_and_final_outcome() -> None:
    response = InsightService(
        RuleBasedAnalysisPlanner(), CountingSQLRunner(), DeterministicInsightWriter()
    ).run(AnalysisRequest(persona="marketer", question="요즘 잘 나가는 상품을 보여줘."))

    assert response.status == "clarification"
    assert len({event.request_id for event in response.trace}) == 1
    assert response.trace[0].stage == "request"
    assert response.trace[0].status == "started"
    assert response.trace[-1].stage == "request"
    assert response.trace[-1].detail["outcome"] == "clarification"
    sql_event = next(event for event in response.trace if event.stage == "sql")
    assert sql_event.status == "skipped"
    assert sql_event.detail["tools_called"] == []


def test_empty_result_returns_safe_error() -> None:
    response = InsightService(
        RuleBasedAnalysisPlanner(),
        ArtifactRunner(_target_artifact([])),
        DeterministicInsightWriter(),
    ).run(AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?"))
    assert response.status == "error"
    assert "데이터가 없습니다" in (response.user_message or "")
    assert response.dataframe is not None and response.dataframe.empty


class TimeoutRunner:
    def run(self, _plan):  # noqa: ANN001, ANN201
        raise QueryExecutionError("timeout", "SQL 실행 시간이 제한을 초과했습니다.")


def test_timeout_returns_safe_error() -> None:
    response = InsightService(
        RuleBasedAnalysisPlanner(), TimeoutRunner(), DeterministicInsightWriter()
    ).run(AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?"))
    assert response.status == "error"
    assert response.user_message == "SQL 실행 시간이 제한을 초과했습니다."
    assert response.trace[-2].detail["category"] == "timeout"


class ParserFailurePlanner:
    def plan(self, _request):  # noqa: ANN001, ANN201
        raise ValueError("raw parser internals")


def test_structured_output_failure_is_safe() -> None:
    runner = CountingSQLRunner()
    response = InsightService(
        ParserFailurePlanner(), runner, DeterministicInsightWriter()
    ).run(AnalysisRequest(persona="planner", question="매출을 보여줘."))
    assert response.status == "error"
    assert "raw parser internals" not in (response.user_message or "")
    assert runner.calls == 0


class FailOnceRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, _plan):  # noqa: ANN001, ANN201
        self.calls += 1
        if self.calls == 1:
            raise QueryExecutionError("database", "PostgreSQL 조회 중 오류가 발생했습니다.")
        return _target_artifact()


def test_failed_request_does_not_affect_next_request() -> None:
    runner = FailOnceRunner()
    service = InsightService(
        RuleBasedAnalysisPlanner(), runner, DeterministicInsightWriter()
    )
    request = AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?")
    first = service.run(request)
    second = service.run(request)
    assert first.status == "error"
    assert second.status == "success"
    assert first.trace[0].request_id != second.trace[0].request_id


def test_renderer_failure_keeps_success_and_dataframe_fallback() -> None:
    service = InsightService(
        RuleBasedAnalysisPlanner(),
        ArtifactRunner(_target_artifact()),
        DeterministicInsightWriter(),
        chart_renderer=lambda _frame, _spec: (None, "차트 실패: 표만 표시합니다."),
    )
    response = service.run(
        AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?")
    )
    assert response.status == "success"
    assert response.figure is None
    assert isinstance(response.dataframe, pd.DataFrame) and not response.dataframe.empty
    assert response.insight is not None
    assert "표만 표시" in response.insight.caveats[-1]
    sql_event = next(event for event in response.trace if event.stage == "sql")
    assert sql_event.detail["final_sql"] == response.query.sql
