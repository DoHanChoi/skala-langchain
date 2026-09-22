#!/usr/bin/env python3
"""Capture actual Gradio UI states at 1440x1000 / 2x using Playwright."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "assets" / "screenshots"
URL = "http://127.0.0.1:7861"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def wait_for_server(timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(URL, timeout=1) as response:  # noqa: S310
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Gradio capture server did not become ready")


def ready(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function("document.fonts && document.fonts.status === 'loaded'")
    page.get_by_role("button", name="분석 실행").wait_for(state="visible")


def select_persona(page: Page, key: str) -> None:
    labels = {
        "planner": "기획자 (planner)",
        "marketer": "마케터 (marketer)",
        "pm": "PM (pm)",
    }
    page.get_by_label(labels[key], exact=True).check()


def analyze(page: Page, persona: str, question: str, expected: str) -> None:
    select_persona(page, persona)
    box = page.get_by_label("데이터 질문")
    box.fill(question)
    page.get_by_role("button", name="분석 실행").click()
    page.get_by_text(expected, exact=False).wait_for(state="visible", timeout=60_000)
    page.wait_for_timeout(350)


def crop_full(source: Path, target: Path, top: int, bottom: int) -> None:
    with Image.open(source) as image:
        bottom = min(bottom, image.height)
        image.crop((0, top, image.width, bottom)).save(target)


def build_comparison(left: Path, right: Path, target: Path) -> None:
    with Image.open(left) as a, Image.open(right) as b:
        width = 1320
        panel_w = 640
        panel_h = 650
        canvas = Image.new("RGB", (width, 760), "#F7F4EE")
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 30)
        except OSError:
            font = ImageFont.load_default()
        for image, x, label in ((a, 0, "기획자"), (b, 680, "마케터")):
            thumb = image.copy()
            thumb.thumbnail((panel_w, panel_h))
            canvas.paste(thumb, (x, 70))
            draw.text((x + 10, 18), label, fill="#18222D", font=font)
        draw.line((655, 20, 655, 735), fill="#D9D6CF", width=2)
        canvas.save(target)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    server_log = ROOT / "reports" / "evidence" / "capture-server.log"
    log_handle = server_log.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "reports" / "serve_capture_app.py")],
        cwd=ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_server()
        with sync_playwright() as playwright:
            launch_kwargs = {"headless": True}
            if CHROME.exists():
                launch_kwargs["executable_path"] = str(CHROME)
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                device_scale_factor=2,
                color_scheme="light",
                reduced_motion="reduce",
                locale="ko-KR",
            )
            page = context.new_page()
            page.goto(URL, wait_until="domcontentloaded")
            ready(page)
            page.screenshot(path=OUT / "01-home.png", full_page=True)

            marketer_question = "최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘."
            analyze(page, "marketer", marketer_question, "분석을 완료했습니다")
            page.screenshot(path=OUT / "02-marketer-result-full.png", full_page=True)
            crop_full(
                OUT / "02-marketer-result-full.png",
                OUT / "02-marketer-result.png",
                0,
                1700,
            )
            page.get_by_role("tab", name="근거").click()
            page.get_by_text("데이터 기준일", exact=False).wait_for(state="visible")
            page.screenshot(path=OUT / "03-marketer-evidence-full.png", full_page=True)
            crop_full(
                OUT / "03-marketer-evidence-full.png",
                OUT / "03-marketer-evidence.png",
                450,
                2200,
            )

            analyze(page, "planner", "최근 신규 고객 수가 어떻게 변했어?", "분석을 완료했습니다")
            page.get_by_role("tab", name="인사이트").click()
            page.screenshot(path=OUT / "04a-planner-common.png", full_page=True)
            analyze(page, "marketer", "최근 신규 고객 수가 어떻게 변했어?", "분석을 완료했습니다")
            page.get_by_role("tab", name="인사이트").click()
            page.screenshot(path=OUT / "04b-marketer-common.png", full_page=True)
            build_comparison(
                OUT / "04a-planner-common.png",
                OUT / "04b-marketer-common.png",
                OUT / "04-persona-comparison.png",
            )

            analyze(page, "marketer", "요즘 잘 나가는 상품을 보여줘.", "확인이 필요합니다")
            page.screenshot(path=OUT / "05-clarification.png", full_page=True)
            context.close()
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log_handle.close()
    print(f"screenshots={OUT}")


if __name__ == "__main__":
    main()
