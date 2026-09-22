"""Pydantic contracts shared by chains, service, tests, and UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Persona = Literal["planner", "marketer", "pm"]


class ChartType(StrEnum):
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    GROUPED_BAR = "grouped_bar"
    STACKED_BAR = "stacked_bar"
    LINE = "line"
    SCATTER = "scatter"
    KPI = "kpi"


class AnalysisRequest(BaseModel):
    persona: Persona
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("질문은 공백일 수 없습니다.")
        return normalized


class AnalysisPlan(BaseModel):
    persona: Persona
    interpreted_question: str
    metric: str
    dimensions: list[str]
    filters: list[str]
    date_range: str
    comparison: str | None = None
    chart_hint: ChartType
    clarification_needed: bool = False
    clarification_question: str | None = None

    @model_validator(mode="after")
    def require_clarification_question(self) -> AnalysisPlan:
        if self.clarification_needed and not self.clarification_question:
            raise ValueError("clarification_needed requires one clarification_question")
        if not self.clarification_needed:
            self.clarification_question = None
        return self


class QueryArtifact(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    source_tables: list[str]
    row_count: int = Field(ge=0)
    data_as_of: date
    attempts: int = Field(ge=1, le=3)


class ChartSpec(BaseModel):
    chart_type: ChartType
    x: str | None = None
    y: str | None = None
    series: str | None = None
    title: str
    x_label: str | None = None
    y_label: str | None = None
    sort: Literal["none", "ascending", "descending"] = "none"
    top_n: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode="after")
    def validate_required_axes(self) -> ChartSpec:
        if self.chart_type == ChartType.KPI:
            if not self.y:
                raise ValueError("kpi chart requires y")
            return self
        if not self.x or not self.y:
            raise ValueError(f"{self.chart_type} chart requires x and y")
        if self.chart_type in {ChartType.GROUPED_BAR, ChartType.STACKED_BAR} and not self.series:
            raise ValueError(f"{self.chart_type} chart requires series")
        return self


class ComputedMetric(BaseModel):
    name: str
    value: float | int | str | None
    formula: str
    unit: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class InsightCard(BaseModel):
    persona: Persona
    question: str
    headline: str
    key_findings: list[str] = Field(min_length=2, max_length=3)
    chart_spec: ChartSpec
    applied_context: list[str]
    next_analysis_question: str
    caveats: list[str] = Field(default_factory=list, max_length=2)
    sql: str
    source_tables: list[str]
    row_count: int = Field(ge=0)
    data_as_of: date


class TraceEvent(BaseModel):
    request_id: str = Field(min_length=32, max_length=32)
    stage: str
    status: Literal["started", "success", "skipped", "error"]
    detail: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Literal["success", "clarification", "error"]
    insight: InsightCard | None = None
    query: QueryArtifact | None = None
    chart_spec: ChartSpec | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    user_message: str | None = None
    dataframe: Any | None = Field(default=None, exclude=True)
    figure: Any | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_status_payload(self) -> AnalysisResponse:
        if self.status == "success" and (self.insight is None or self.query is None):
            raise ValueError("success response requires insight and query")
        if self.status != "success" and not self.user_message:
            raise ValueError("non-success response requires user_message")
        return self
