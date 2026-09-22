"""Gradio Blocks UI that depends only on the InsightService contract."""

from __future__ import annotations

import html
from typing import Any

import gradio as gr
import pandas as pd
from pydantic import ValidationError

from rolelens.agents.model import require_model_credentials
from rolelens.config import get_settings
from rolelens.domain.models import AnalysisRequest, AnalysisResponse
from rolelens.domain.personas import EXAMPLE_QUESTIONS, PERSONAS
from rolelens.services.insight_service import InsightService, build_service


def _list_markdown(items: list[str]) -> str:
    return "\n".join(f"- {html.escape(str(item))}" for item in items)


def format_response(response: AnalysisResponse) -> tuple[str, str, Any, pd.DataFrame, str, str]:
    """Map service DTO to the four UI result areas without touching DB or chains."""

    if response.status == "clarification":
        return (
            f"🟡 **확인이 필요합니다.** {html.escape(response.user_message or '')}",
            "",
            None,
            pd.DataFrame(),
            "",
            "",
        )
    if response.status == "error" or response.insight is None or response.query is None:
        return (
            f"🔴 **분석을 완료하지 못했습니다.** {html.escape(response.user_message or '')}",
            "",
            None,
            response.dataframe if isinstance(response.dataframe, pd.DataFrame) else pd.DataFrame(),
            "",
            "",
        )

    insight = response.insight
    insight_markdown = (
        f"### {html.escape(insight.headline)}\n\n"
        f"**주요 발견**\n\n{_list_markdown(insight.key_findings)}\n\n"
        f"**다음 분석 질문**\n\n{html.escape(insight.next_analysis_question)}"
    )
    if insight.caveats:
        insight_markdown += f"\n\n**주의사항**\n\n{_list_markdown(insight.caveats)}"

    evidence_markdown = (
        f"**페르소나:** `{insight.persona}`  \n"
        f"**적용 기준:**\n{_list_markdown(insight.applied_context)}\n\n"
        f"**사용 테이블:** {', '.join(f'`analytics.{name}`' for name in insight.source_tables)}  \n"
        f"**조회 행 수:** {insight.row_count}  \n"
        f"**데이터 기준일:** {insight.data_as_of.isoformat()}"
    )
    dataframe = response.dataframe if isinstance(response.dataframe, pd.DataFrame) else pd.DataFrame(response.query.rows)
    return (
        "🟢 **분석을 완료했습니다.**",
        insight_markdown,
        response.figure,
        dataframe,
        evidence_markdown,
        insight.sql,
    )


def analyze_from_ui(
    service: InsightService, persona: str, question: str
) -> tuple[str, str, Any, pd.DataFrame, str, str]:
    try:
        request = AnalysisRequest(persona=persona, question=question)
    except ValidationError:
        return (
            "🔴 **입력을 확인하세요.** 페르소나를 선택하고 1~500자의 질문을 입력하세요.",
            "",
            None,
            pd.DataFrame(),
            "",
            "",
        )
    return format_response(service.run(request))


def build_app(service: InsightService | None = None) -> gr.Blocks:
    if service is None:
        settings = get_settings()
        require_model_credentials(settings)
        service = build_service(settings)

    with gr.Blocks(title="RoleLens") as app:
        gr.Markdown(
            "# RoleLens\n"
            "기획자·마케터·PM의 관점으로 Mock 커머스 데이터를 안전하게 분석합니다."
        )
        with gr.Row():
            persona = gr.Radio(
                choices=[
                    (f"{profile.label} ({key})", key) for key, profile in PERSONAS.items()
                ],
                value="planner",
                label="분석 관점",
            )
            question = gr.Textbox(
                value=EXAMPLE_QUESTIONS["planner"],
                label="데이터 질문",
                lines=3,
                max_lines=6,
                placeholder="자연어로 질문하세요.",
            )
        analyze_button = gr.Button("분석 실행", variant="primary")
        status = gr.Markdown()

        with gr.Tabs():
            with gr.Tab("인사이트"):
                insight = gr.Markdown()
            with gr.Tab("시각화"):
                chart = gr.Plot(label="검증된 ChartSpec 결과")
            with gr.Tab("데이터"):
                data = gr.Dataframe(interactive=False, label="조회 결과")
            with gr.Tab("근거"):
                evidence = gr.Markdown()
                sql = gr.Code(language="sql", label="최종 실행 SQL", interactive=False)

        persona.change(
            fn=lambda selected: EXAMPLE_QUESTIONS[selected],
            inputs=persona,
            outputs=question,
            show_progress="hidden",
        )
        analyze_button.click(
            fn=lambda selected, prompt: analyze_from_ui(service, selected, prompt),
            inputs=[persona, question],
            outputs=[status, insight, chart, data, evidence, sql],
        )
    return app


def main() -> None:
    build_app().queue(default_concurrency_limit=1).launch(theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
