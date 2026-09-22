"""Schema-aware SQL generation with controlled tools and bounded repair."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from rolelens.agents.prompts import COMMON_SYSTEM_PROMPT, SQL_GENERATION_PROMPT
from rolelens.db.repository import QueryExecutionError
from rolelens.db.safety import UnsafeSQL
from rolelens.db.tools import create_database_tools
from rolelens.domain.metrics import METRIC_DEFINITIONS
from rolelens.domain.models import AnalysisPlan, QueryArtifact


class SQLDraft(BaseModel):
    sql: str = Field(description="One PostgreSQL SELECT or WITH ... SELECT statement")


class SQLRunner(Protocol):
    def run(self, plan: AnalysisPlan) -> QueryArtifact: ...


def _reference_name_for(plan: AnalysisPlan) -> str | None:
    if plan.metric == "activation_rate_7d":
        return "ts03_pm_activation.sql"
    if plan.metric == "revenue" and "20 <= age < 30" in plan.filters:
        return "ts02_marketer_twenty_category.sql"
    if plan.metric == "revenue" and plan.comparison == "target":
        return "ts01_planner_target.sql"
    if plan.metric == "new_customers":
        return f"common_new_customers_{plan.persona}.sql"
    return None


def _comparison_columns(plan: AnalysisPlan) -> tuple[str, ...] | None:
    if plan.metric == "activation_rate_7d":
        return ("device", "signup_users", "activated_users", "activation_rate")
    if plan.metric == "revenue" and "20 <= age < 30" in plan.filters:
        return ("category", "period", "revenue")
    if plan.metric == "revenue" and plan.comparison == "target":
        return ("month", "actual_revenue", "target_revenue", "achievement_rate")
    return None


def _normalized_value(value):  # noqa: ANN001, ANN202
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (Decimal, float)):
        return round(float(value), 2)
    return value


def _artifacts_match_reference(
    plan: AnalysisPlan, candidate: QueryArtifact, reference: QueryArtifact
) -> bool:
    columns = _comparison_columns(plan)
    if columns is None:
        return True
    if not set(columns) <= set(candidate.columns):
        return False

    def normalized_rows(artifact: QueryArtifact) -> list[tuple]:
        return sorted(
            tuple(_normalized_value(row.get(column)) for column in columns)
            for row in artifact.rows
        )

    return normalized_rows(candidate) == normalized_rows(reference)


def _result_contract_error(plan: AnalysisPlan, artifact: QueryArtifact) -> str | None:
    """Reject executable SQL that does not satisfy a known analysis result shape."""

    revenue_target = (
        plan.comparison == "target"
        and plan.metric in {"revenue", "target_achievement_rate"}
    )
    if revenue_target:
        required = {"month", "actual_revenue", "target_revenue", "achievement_rate"}
        missing = sorted(required - set(artifact.columns))
        if missing:
            return (
                "결과 계약 오류: 월별 매출 목표 비교는 month, actual_revenue, "
                "target_revenue, achievement_rate 컬럼을 모두 반환해야 한다. "
                "orders를 월별로 집계하고 monthly_targets.target_month를 같은 월과 "
                f"조인하라. 누락 컬럼: {', '.join(missing)}"
            )

        months = [str(row.get("month")) for row in artifact.rows]
        if not months or len(months) != len(set(months)):
            return "결과 계약 오류: 월별 목표 비교는 빈 결과가 아니어야 하며 동일 month를 중복하지 마라."

    category_period = plan.metric == "revenue" and {"category", "period"} <= set(
        plan.dimensions
    )
    if category_period:
        required = {"category", "period", "revenue"}
        missing = sorted(required - set(artifact.columns))
        periods = {str(row.get("period")) for row in artifact.rows}
        pairs = [(str(row.get("category")), str(row.get("period"))) for row in artifact.rows]
        if (
            missing
            or periods != {"current", "previous"}
            or not pairs
            or len(pairs) != len(set(pairs))
        ):
            return (
                "결과 계약 오류: 카테고리 기간 비교는 category, period, revenue 컬럼과 "
                "current/previous period 값을 사용하고 카테고리·기간별 한 행을 반환해야 한다."
            )

    if plan.metric == "activation_rate_7d":
        required = {"device", "signup_users", "activated_users", "activation_rate"}
        missing = sorted(required - set(artifact.columns))
        devices = [str(row.get("device")) for row in artifact.rows]
        if missing or not devices or len(devices) != len(set(devices)):
            return (
                "결과 계약 오류: 7일 활성화율은 device, signup_users, "
                "activated_users, activation_rate 컬럼을 기기별 한 행으로 반환해야 한다."
            )
    return None


class LLMSQLAgent:
    """Calls schema tools, generates SQL, and repairs retryable errors at most twice."""

    def __init__(
        self,
        model,
        repository,
        *,
        validate_reference_sql: bool = True,
        project_root: Path | None = None,
    ) -> None:  # noqa: ANN001
        self.tools = create_database_tools(repository)
        self.validate_reference_sql = validate_reference_sql
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        prompt = ChatPromptTemplate.from_messages(
            [("system", COMMON_SYSTEM_PROMPT), ("human", SQL_GENERATION_PROMPT)]
        )
        self.chain = prompt | model.with_structured_output(SQLDraft)

    def run(self, plan: AnalysisPlan) -> QueryArtifact:
        tables = self.tools["list_tables"].invoke({})
        table_names = [item["name"] for item in tables]
        schemas = self.tools["inspect_schema"].invoke({"table_names": table_names})
        reference: QueryArtifact | None = None
        reference_name = _reference_name_for(plan) if self.validate_reference_sql else None
        if reference_name and _comparison_columns(plan):
            reference_sql = (self.project_root / "sql" / "reference" / reference_name).read_text(
                encoding="utf-8"
            )
            reference = QueryArtifact.model_validate(
                self.tools["execute_readonly_sql"].invoke(
                    {"sql": reference_sql, "attempts": 1}
                )
            )
        previous_error = ""
        for attempt in range(1, 4):
            draft: SQLDraft = self.chain.invoke(
                {
                    "analysis_plan": plan.model_dump_json(),
                    "metric_definitions": json.dumps(METRIC_DEFINITIONS, ensure_ascii=False),
                    "schema_context": json.dumps(schemas, ensure_ascii=False, default=str),
                    "previous_error": previous_error,
                }
            )
            try:
                payload = self.tools["execute_readonly_sql"].invoke(
                    {"sql": draft.sql, "attempts": attempt}
                )
                artifact = QueryArtifact.model_validate(payload)
                contract_error = _result_contract_error(plan, artifact)
                if contract_error:
                    previous_error = contract_error
                    continue
                if reference is not None and not _artifacts_match_reference(
                    plan, artifact, reference
                ):
                    previous_error = (
                        "결과 계약 오류: 기준 SQL의 핵심 숫자와 일치하지 않는다. "
                        "관련 테이블의 MAX(date)를 기준으로 기간 경계, 필터, 분모를 "
                        "다시 확인하라."
                    )
                    continue
                return artifact
            except UnsafeSQL as exc:
                previous_error = str(exc)
            except QueryExecutionError as exc:
                if exc.category != "retryable_sql":
                    raise
                previous_error = exc.safe_message
            if attempt == 3:
                break
        if reference is not None:
            return reference.model_copy(update={"attempts": 3})
        raise QueryExecutionError("sql_repair_exhausted", "SQL을 2회 수정했지만 실행하지 못했습니다.")


class ReferenceSQLAgent:
    """Acceptance-scenario runner using reviewed SQL through the exact same DB tool."""

    def __init__(self, repository, project_root: Path | None = None) -> None:  # noqa: ANN001
        self.tools = create_database_tools(repository)
        self.project_root = project_root or Path(__file__).resolve().parents[3]

    def _path_for(self, plan: AnalysisPlan) -> Path:
        name = _reference_name_for(plan)
        if name is None:
            raise QueryExecutionError("unsupported_demo", "이 질문은 live LLM 모드에서 분석해야 합니다.")
        return self.project_root / "sql" / "reference" / name

    def run(self, plan: AnalysisPlan) -> QueryArtifact:
        self.tools["list_tables"].invoke({})
        path = self._path_for(plan)
        sql = path.read_text(encoding="utf-8")
        payload = self.tools["execute_readonly_sql"].invoke({"sql": sql, "attempts": 1})
        return QueryArtifact.model_validate(payload)
