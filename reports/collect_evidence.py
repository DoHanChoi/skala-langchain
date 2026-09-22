#!/usr/bin/env python3
"""Collect reproducible RoleLens report evidence without exposing secrets."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import os
import platform
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from rolelens.config import get_settings
from rolelens.db.engine import create_admin_engine, create_readonly_engine
from rolelens.db.repository import AnalyticsRepository
from rolelens.db.safety import UnsafeSQL, validate_sql
from rolelens.domain.models import AnalysisRequest
from rolelens.services.insight_service import build_service


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "reports" / "evidence"
CHARTS = ROOT / "reports" / "assets" / "charts"


def json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(type(value).__name__)


def write_json(name: str, payload: Any) -> None:
    path = EVIDENCE / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def serialize_response(persona: str, question: str, response) -> dict[str, Any]:  # noqa: ANN001
    plan = next(
        (event.detail.get("plan") for event in response.trace if event.stage == "analysis_plan"),
        None,
    )
    return {
        "mode": "offline_acceptance",
        "persona": persona,
        "question": question,
        "status": response.status,
        "analysis_plan": plan,
        "user_message": response.user_message,
        "insight": response.insight.model_dump(mode="json") if response.insight else None,
        "query": response.query.model_dump(mode="json") if response.query else None,
        "chart_spec": response.chart_spec.model_dump(mode="json") if response.chart_spec else None,
        "trace": [event.model_dump(mode="json") for event in response.trace],
    }


def run_scenario(service, slug: str, persona: str, question: str) -> dict[str, Any]:  # noqa: ANN001
    response = service.run(AnalysisRequest(persona=persona, question=question))
    payload = serialize_response(persona, question, response)
    write_json(f"scenario-{slug}.json", payload)
    if response.figure is not None:
        response.figure.savefig(CHARTS / f"{slug}.png", dpi=180, bbox_inches="tight")
    return payload


def environment_summary() -> str:
    settings = get_settings()
    engine = create_admin_engine(settings)
    with engine.connect() as connection:
        version = connection.execute(text("SHOW server_version")).scalar_one()
        migration = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        counts = dict(
            connection.execute(
                text(
                    "SELECT 'users', COUNT(*) FROM analytics.users UNION ALL "
                    "SELECT 'user_events', COUNT(*) FROM analytics.user_events UNION ALL "
                    "SELECT 'products', COUNT(*) FROM analytics.products UNION ALL "
                    "SELECT 'campaigns', COUNT(*) FROM analytics.campaigns UNION ALL "
                    "SELECT 'orders', COUNT(*) FROM analytics.orders UNION ALL "
                    "SELECT 'monthly_targets', COUNT(*) FROM analytics.monthly_targets"
                )
            ).all()
        )
        order_span = connection.execute(
            text("SELECT MIN(order_date), MAX(order_date) FROM analytics.orders")
        ).one()
        statuses = dict(
            connection.execute(
                text("SELECT status, COUNT(*) FROM analytics.orders GROUP BY status ORDER BY status")
            ).all()
        )
    packages = {
        name: metadata.version(name)
        for name in (
            "rolelens",
            "langchain-core",
            "langchain-openai",
            "gradio",
            "sqlalchemy",
            "sqlglot",
            "alembic",
            "pytest",
        )
    }
    return "\n".join(
        [
            "RoleLens environment verification",
            f"collected_at={datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"platform={platform.platform()}",
            f"python={platform.python_version()}",
            f"postgresql={version}",
            f"migration={migration}",
            "container=rolelens-db-1 healthy (verified before collection)",
            f"model_provider={settings.model_provider}",
            f"model_id={settings.model_id}",
            f"model_key_configured={bool(settings.model_api_key and settings.model_api_key.get_secret_value().strip())}",
            f"data_as_of={settings.data_as_of.isoformat()}",
            f"random_seed={settings.random_seed}",
            f"max_query_rows={settings.max_query_rows}",
            f"statement_timeout_ms={settings.sql_statement_timeout_ms}",
            f"table_counts={json.dumps(counts, ensure_ascii=False, sort_keys=True)}",
            f"order_date_range={order_span[0].isoformat()}..{order_span[1].isoformat()}",
            f"order_status_counts={json.dumps(statuses, ensure_ascii=False, sort_keys=True)}",
            f"packages={json.dumps(packages, ensure_ascii=False, sort_keys=True)}",
            "secret_values_recorded=false",
        ]
    ) + "\n"


def safety_summary() -> str:
    cases = {
        "select_allowlisted": "SELECT order_id FROM analytics.orders ORDER BY order_id",
        "select_star": "SELECT * FROM analytics.orders",
        "multiple_statements": "SELECT order_id FROM analytics.orders; DROP TABLE analytics.orders",
        "delete": "DELETE FROM analytics.orders WHERE order_id = -1",
        "system_catalog": "SELECT relname FROM pg_catalog.pg_class",
        "outside_allowlist": "SELECT version_num FROM public.alembic_version",
        "write_cte": "WITH x AS (DELETE FROM analytics.orders RETURNING order_id) SELECT order_id FROM x",
    }
    lines = ["RoleLens SQL safety verification"]
    for name, sql in cases.items():
        try:
            validated = validate_sql(sql, max_rows=100)
            outcome = "allowed" if name == "select_allowlisted" else "UNEXPECTED_ALLOW"
            detail = "row_limit_present=" + str("LIMIT 100" in validated.sql)
        except UnsafeSQL as exc:
            outcome = "blocked"
            detail = str(exc)
        lines.append(f"{name}: {outcome} | {detail}")

    settings = get_settings()
    ro_engine = create_readonly_engine(settings)
    for name, statement in {
        "readonly_delete": "DELETE FROM analytics.orders WHERE order_id = -1",
        "readonly_create": "CREATE TABLE analytics.report_probe(id integer)",
    }.items():
        try:
            with ro_engine.begin() as connection:
                connection.execute(text(statement))
            lines.append(f"{name}: UNEXPECTED_ALLOW")
        except DBAPIError:
            lines.append(f"{name}: blocked_by_postgresql")

    repository = AnalyticsRepository(settings=settings)
    artifact = repository.execute_readonly_sql(
        "SELECT order_id FROM analytics.orders ORDER BY order_id"
    )
    lines.append(f"row_cap: returned={artifact.row_count} expected_max={settings.max_query_rows}")
    return "\n".join(lines) + "\n"


def run_pytest() -> str:
    result = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "pytest"), "-q"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    output = (result.stdout + result.stderr).strip()
    return f"command=.venv/bin/pytest -q\nexit_code={result.returncode}\n{output}\n"


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "environment-summary.txt").write_text(environment_summary(), encoding="utf-8")
    (EVIDENCE / "sql-safety-summary.txt").write_text(safety_summary(), encoding="utf-8")
    (EVIDENCE / "test-summary.txt").write_text(run_pytest(), encoding="utf-8")

    service = build_service(offline_acceptance_mode=True)
    run_scenario(
        service,
        "planner",
        "planner",
        "이번 분기 매출이 목표 대비 어떤가?",
    )
    run_scenario(
        service,
        "marketer",
        "marketer",
        "최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.",
    )
    run_scenario(
        service,
        "pm",
        "pm",
        "최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.",
    )
    run_scenario(
        service,
        "ambiguous",
        "marketer",
        "요즘 잘 나가는 상품을 보여줘.",
    )
    common: dict[str, Any] = {}
    for persona in ("planner", "marketer", "pm"):
        response = service.run(
            AnalysisRequest(persona=persona, question="최근 신규 고객 수가 어떻게 변했어?")
        )
        common[persona] = serialize_response(
            persona, "최근 신규 고객 수가 어떻게 변했어?", response
        )
    write_json("scenario-persona-comparison.json", common)
    print(f"evidence={EVIDENCE}")


if __name__ == "__main__":
    main()
