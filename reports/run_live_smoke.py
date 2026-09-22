#!/usr/bin/env python3
"""Run a small live-model smoke test and record only non-secret outcomes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rolelens.config import get_settings
from rolelens.domain.models import AnalysisRequest
from rolelens.services.insight_service import build_service


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "evidence" / "live-model-summary.json"


def main() -> None:
    settings = get_settings()
    service = build_service(settings)
    cases = [
        (
            "marketer",
            "최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.",
        ),
        ("marketer", "요즘 잘 나가는 상품을 보여줘."),
    ]
    results = []
    for persona, question in cases:
        response = service.run(AnalysisRequest(persona=persona, question=question))
        results.append(
            {
                "persona": persona,
                "question": question,
                "status": response.status,
                "message": response.user_message,
                "headline": response.insight.headline if response.insight else None,
                "attempts": response.query.attempts if response.query else None,
                "row_count": response.query.row_count if response.query else None,
                "source_tables": response.query.source_tables if response.query else None,
                "analysis_plan": next(
                    (
                        event.detail.get("plan")
                        for event in response.trace
                        if event.stage == "analysis_plan"
                    ),
                    None,
                ),
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "provider": settings.model_provider,
                "model_id": settings.model_id,
                "secret_values_recorded": False,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"live_smoke={OUT}")


if __name__ == "__main__":
    main()
