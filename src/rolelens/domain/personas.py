"""Fixed persona definitions. Personas never redefine metrics."""

from __future__ import annotations

from dataclasses import dataclass

from rolelens.domain.models import Persona


@dataclass(frozen=True)
class PersonaProfile:
    key: Persona
    label: str
    focus: str
    default_comparison: str
    priority_dimensions: tuple[str, ...]
    follow_up_focus: str


PERSONAS: dict[Persona, PersonaProfile] = {
    "planner": PersonaProfile(
        key="planner",
        label="기획자",
        focus="핵심 KPI, 목표 대비 실적, 이전 동일 기간, 격차 기여도",
        default_comparison="목표 또는 직전 동일 기간",
        priority_dimensions=("월", "카테고리", "지역"),
        follow_up_focus="KPI 격차 구성",
    ),
    "marketer": PersonaProfile(
        key="marketer",
        label="마케터",
        focus="고객 세그먼트, 유입 채널, 캠페인, 매출·전환·재구매",
        default_comparison="직전 동일 기간",
        priority_dimensions=("채널", "캠페인", "세그먼트"),
        follow_up_focus="세그먼트·채널 검증",
    ),
    "pm": PersonaProfile(
        key="pm",
        label="PM",
        focus="사용자 퍼널, 가입 후 활성화, 핵심 기능 사용, 사용자군별 행동 차이",
        default_comparison="퍼널 단계 또는 사용자군",
        priority_dimensions=("기기", "유입경로", "행동 단계"),
        follow_up_focus="이탈·활성화 가설",
    ),
}


EXAMPLE_QUESTIONS: dict[Persona, str] = {
    "planner": "이번 분기 매출이 목표 대비 어떤가?",
    "marketer": "최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.",
    "pm": "최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.",
}
