"""Single application entry point used by notebooks, tests, and Gradio."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from rolelens.agents.insight_writer import (
    DeterministicInsightWriter,
    InsightWriter,
    LLMInsightWriter,
)
from rolelens.agents.model import MissingModelCredentials, create_chat_model
from rolelens.agents.planner import (
    AnalysisPlanner,
    LLMAnalysisPlanner,
    RuleBasedAnalysisPlanner,
)
from rolelens.agents.sql_agent import LLMSQLAgent, ReferenceSQLAgent, SQLRunner
from rolelens.config import Settings, get_settings
from rolelens.db.repository import AnalyticsRepository, QueryExecutionError
from rolelens.db.safety import UnsafeSQL
from rolelens.domain.metrics import analyze_result, artifact_to_dataframe
from rolelens.domain.models import (
    AnalysisRequest,
    AnalysisResponse,
    ChartSpec,
    TraceEvent,
)
from rolelens.visualization.chart_planner import InvalidChartSpec, plan_chart
from rolelens.visualization.renderer import try_render_chart


LOGGER = logging.getLogger(__name__)


class _MissingCredentialPlanner:
    def plan(self, request: AnalysisRequest):  # noqa: ANN201
        raise MissingModelCredentials(
            "MODEL_API_KEY 또는 OPENAI_API_KEY를 .env에 설정한 뒤 다시 시도하세요."
        )


class InsightService:
    """Orchestrates one stateless analysis request across injected components."""

    def __init__(
        self,
        planner: AnalysisPlanner,
        sql_runner: SQLRunner,
        insight_writer: InsightWriter,
        chart_planner: Callable[[Any, Any], ChartSpec] = plan_chart,
        chart_renderer: Callable[[Any, ChartSpec], tuple[Any | None, str | None]] = try_render_chart,
    ) -> None:
        self.planner = planner
        self.sql_runner = sql_runner
        self.insight_writer = insight_writer
        self.chart_planner = chart_planner
        self.chart_renderer = chart_renderer

    @staticmethod
    def _event(request_id: str, stage: str, status: str, **detail: Any) -> TraceEvent:
        return TraceEvent(  # type: ignore[arg-type]
            request_id=request_id,
            stage=stage,
            status=status,
            detail=detail,
        )

    def run(self, request: AnalysisRequest) -> AnalysisResponse:
        request_id = uuid4().hex
        trace: list[TraceEvent] = [
            self._event(request_id, "request", "started", persona=request.persona)
        ]
        started = time.perf_counter()

        def respond(status: str, **payload: Any) -> AnalysisResponse:
            trace.append(
                self._event(
                    request_id,
                    "request",
                    "error" if status == "error" else "success",
                    outcome=status,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            )
            return AnalysisResponse(status=status, trace=trace, **payload)  # type: ignore[arg-type]

        try:
            plan_started = time.perf_counter()
            plan = self.planner.plan(request)
            trace.append(
                self._event(
                    request_id,
                    "analysis_plan",
                    "success",
                    persona=request.persona,
                    plan=plan.model_dump(mode="json"),
                    elapsed_ms=round((time.perf_counter() - plan_started) * 1000, 2),
                )
            )
            if plan.clarification_needed:
                trace.append(
                    self._event(
                        request_id,
                        "sql",
                        "skipped",
                        reason="clarification_needed",
                        tools_called=[],
                    )
                )
                return respond(
                    status="clarification",
                    user_message=plan.clarification_question,
                )

            query_started = time.perf_counter()
            query = self.sql_runner.run(plan)
            trace.append(
                self._event(
                    request_id,
                    "sql",
                    "success",
                    attempts=query.attempts,
                    row_count=query.row_count,
                    source_tables=query.source_tables,
                    tools_called=[
                        "list_tables",
                        "inspect_schema",
                        "execute_readonly_sql",
                    ],
                    final_sql=query.sql,
                    elapsed_ms=round((time.perf_counter() - query_started) * 1000, 2),
                )
            )
            frame = artifact_to_dataframe(query)
            if frame.empty:
                trace.append(
                    self._event(request_id, "dataframe", "error", reason="empty_result")
                )
                return respond(
                    status="error",
                    query=query,
                    dataframe=frame,
                    user_message="조건에 해당하는 데이터가 없습니다. 기간이나 필터를 바꿔 보세요.",
                )

            computed = analyze_result(frame)
            trace.append(
                self._event(
                    request_id,
                    "deterministic_analysis",
                    "success",
                    metrics=[metric.model_dump(mode="json") for metric in computed],
                )
            )

            chart_spec: ChartSpec = self.chart_planner(plan, frame)
            figure, chart_error = self.chart_renderer(frame, chart_spec)
            trace.append(
                self._event(
                    request_id,
                    "chart",
                    "success" if figure is not None else "error",
                    chart_spec=chart_spec.model_dump(mode="json"),
                    fallback=chart_error,
                )
            )

            insight = self.insight_writer.write(request, plan, query, computed, chart_spec)
            if chart_error and len(insight.caveats) < 2:
                insight.caveats.append(chart_error)
            trace.append(
                self._event(
                    request_id,
                    "insight",
                    "success",
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            )
            return respond(
                status="success",
                insight=insight,
                query=query,
                chart_spec=chart_spec,
                dataframe=frame,
                figure=figure,
            )
        except MissingModelCredentials as exc:
            trace.append(
                self._event(request_id, "model", "error", category="missing_credentials")
            )
            return respond(status="error", user_message=str(exc))
        except (UnsafeSQL, InvalidChartSpec) as exc:
            trace.append(
                self._event(
                    request_id, "safety", "error", category=type(exc).__name__
                )
            )
            return respond(
                status="error",
                user_message=f"안전 규칙에 따라 분석을 중단했습니다: {exc}",
            )
        except QueryExecutionError as exc:
            trace.append(
                self._event(request_id, "sql", "error", category=exc.category)
            )
            return respond(status="error", user_message=exc.safe_message)
        except Exception as exc:  # keep UI process alive; details go only to local logs
            LOGGER.exception("RoleLens request failed", extra={"persona": request.persona})
            trace.append(
                self._event(
                    request_id, "service", "error", category=type(exc).__name__
                )
            )
            return respond(
                status="error",
                user_message="분석 중 예상하지 못한 오류가 발생했습니다. DB와 모델 설정을 확인하세요.",
            )


def build_service(
    settings: Settings | None = None,
    *,
    offline_acceptance_mode: bool = False,
) -> InsightService:
    """Build live service, or deterministic acceptance service when explicitly requested."""

    settings = settings or get_settings()
    repository = AnalyticsRepository(settings=settings)
    if offline_acceptance_mode:
        return InsightService(
            planner=RuleBasedAnalysisPlanner(),
            sql_runner=ReferenceSQLAgent(repository),
            insight_writer=DeterministicInsightWriter(),
        )
    try:
        model = create_chat_model(settings)
    except MissingModelCredentials:
        return InsightService(
            planner=_MissingCredentialPlanner(),
            sql_runner=ReferenceSQLAgent(repository),
            insight_writer=DeterministicInsightWriter(),
        )
    return InsightService(
        planner=LLMAnalysisPlanner(model),
        sql_runner=LLMSQLAgent(model, repository),
        insight_writer=LLMInsightWriter(model),
    )
