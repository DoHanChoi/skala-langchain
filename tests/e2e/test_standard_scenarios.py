from __future__ import annotations

import pytest

from rolelens.domain.models import AnalysisRequest
from rolelens.services.insight_service import build_service
from rolelens.ui.gradio_app import build_app, format_response


pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    ("persona", "question", "tables"),
    [
        ("planner", "이번 분기 매출이 목표 대비 어떤가?", {"orders", "monthly_targets"}),
        (
            "marketer",
            "최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.",
            {"users", "orders", "products"},
        ),
        (
            "pm",
            "최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.",
            {"users", "user_events"},
        ),
    ],
)
def test_standard_scenario(require_postgres, persona, question, tables) -> None:  # noqa: ANN001
    service = build_service(require_postgres, offline_acceptance_mode=True)
    response = service.run(AnalysisRequest(persona=persona, question=question))
    assert response.status == "success"
    assert response.figure is not None
    assert response.query is not None and set(response.query.source_tables) == tables
    assert response.insight is not None and len(response.insight.key_findings) in {2, 3}
    assert format_response(response)[0].startswith("🟢")


def test_standard_scenario_numbers_are_grounded(require_postgres) -> None:  # noqa: ANN001
    service = build_service(require_postgres, offline_acceptance_mode=True)

    planner = service.run(
        AnalysisRequest(persona="planner", question="이번 분기 매출이 목표 대비 어떤가?")
    )
    marketer = service.run(
        AnalysisRequest(
            persona="marketer",
            question="최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.",
        )
    )
    pm = service.run(
        AnalysisRequest(
            persona="pm",
            question="최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.",
        )
    )

    assert planner.insight is not None and "95.69%" in planner.insight.headline
    assert marketer.insight is not None and "9,224,189원" in marketer.insight.headline
    assert pm.insight is not None and "66.67%" in pm.insight.headline
    assert any("43.06%" in item for item in pm.insight.key_findings)


@pytest.mark.parametrize(
    ("persona", "expected_columns", "expected_chart"),
    [
        ("planner", {"month", "new_customers", "target_new_customers"}, "grouped_bar"),
        (
            "marketer",
            {"month", "acquisition_channel", "new_customers"},
            "stacked_bar",
        ),
        (
            "pm",
            {"device", "new_customers", "activated_new_customers", "activation_rate"},
            "bar",
        ),
    ],
)
def test_common_question_has_persona_specific_result(
    require_postgres, persona, expected_columns, expected_chart
) -> None:  # noqa: ANN001
    service = build_service(require_postgres, offline_acceptance_mode=True)
    response = service.run(
        AnalysisRequest(persona=persona, question="최근 신규 고객 수가 어떻게 변했어?")
    )

    assert response.status == "success"
    assert response.query is not None
    assert set(response.query.columns) == expected_columns
    assert response.chart_spec is not None
    assert response.chart_spec.chart_type == expected_chart


def test_gradio_builds_from_service(require_postgres) -> None:  # noqa: ANN001
    app = build_app(build_service(require_postgres, offline_acceptance_mode=True))
    assert app is not None
