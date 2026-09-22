#!/usr/bin/env python3
"""Build and validate the final RoleLens Korean A4 PDF report."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import pdfplumber
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from playwright.sync_api import sync_playwright
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EVIDENCE = REPORTS / "evidence"
ASSETS = REPORTS / "assets"
DIAGRAMS = ASSETS / "diagrams"
TEMPLATES = REPORTS / "templates"
STYLES = REPORTS / "styles"
TMP = ROOT / "tmp" / "pdfs"
RENDERED = TMP / "rendered-pages"
VALIDATION = TMP / "validation"
OUTPUT = ROOT / "output" / "pdf"
HTML_OUT = TMP / "RoleLens_서비스보고서.html"
PDF_OUT = OUTPUT / "RoleLens_서비스보고서.pdf"
STABILITY_PDF = VALIDATION / "RoleLens_서비스보고서-second-pass.pdf"
CHROME = Path(
    os.environ.get(
        "CHROME_PATH",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
)

logging.getLogger("pdfminer").setLevel(logging.ERROR)

DIAGRAM_SKILL = Path(os.environ.get("DIAGRAM_SKILL_DIR", ""))
SELF_CHECK = DIAGRAM_SKILL / "skills" / "diagram-design" / "scripts" / "self_check.py"
GEOMETRY_CHECK = DIAGRAM_SKILL / "scripts" / "verify-geometry.py"


def require_inputs() -> None:
    if not os.environ.get("DIAGRAM_SKILL_DIR"):
        raise EnvironmentError("DIAGRAM_SKILL_DIR must point to the diagram-design plugin")
    required = [
        EVIDENCE / "environment-summary.txt",
        EVIDENCE / "test-summary.txt",
        EVIDENCE / "sql-safety-summary.txt",
        EVIDENCE / "scenario-marketer.json",
        EVIDENCE / "scenario-planner.json",
        EVIDENCE / "scenario-pm.json",
        EVIDENCE / "scenario-ambiguous.json",
        EVIDENCE / "scenario-persona-comparison.json",
        ASSETS / "charts" / "marketer.png",
        ASSETS / "screenshots" / "02-marketer-result.png",
        ASSETS / "screenshots" / "04-persona-comparison.png",
        ASSETS / "screenshots" / "05-clarification.png",
        DIAGRAMS / "analysis-flow.html",
        DIAGRAMS / "sql-safety.html",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing report inputs. Run evidence/capture first: " + ", ".join(missing)
        )


def verify_and_export_diagram(html_path: Path) -> Path:
    subprocess.run(["python3", str(SELF_CHECK), str(html_path)], check=True, cwd=ROOT)
    subprocess.run(["python3", str(GEOMETRY_CHECK), str(html_path)], check=True, cwd=ROOT)
    text = html_path.read_text(encoding="utf-8")
    match = re.search(r"<svg\b[\s\S]*?</svg>", text)
    if not match:
        raise ValueError(f"No SVG found in {html_path}")
    svg = match.group(0)
    if "xmlns=" not in svg.split(">", 1)[0]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    svg_path = html_path.with_suffix(".svg")
    svg_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + svg + "\n", encoding="utf-8")
    return svg_path


def write_report_data() -> dict:
    marketer = json.loads((EVIDENCE / "scenario-marketer.json").read_text(encoding="utf-8"))
    planner = json.loads((EVIDENCE / "scenario-planner.json").read_text(encoding="utf-8"))
    pm = json.loads((EVIDENCE / "scenario-pm.json").read_text(encoding="utf-8"))
    data = {
        "data_as_of": marketer["query"]["data_as_of"],
        "scenarios": {"marketer": marketer, "planner": planner, "pm": pm},
        "evidence_files": sorted(path.name for path in EVIDENCE.iterdir() if path.is_file()),
        "source_commit": "not recorded; working tree preserved",
    }
    (REPORTS / "report_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


def render_html(data: dict, analysis_svg: Path, safety_svg: Path) -> None:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        autoescape=True,
    )
    template = environment.get_template("rolelens_report.html.j2")
    css = (STYLES / "report.css").read_text(encoding="utf-8")
    html = template.render(
        css=css,
        data_as_of=data["data_as_of"],
        analysis_flow_uri=analysis_svg.resolve().as_uri(),
        sql_safety_uri=safety_svg.resolve().as_uri(),
        marketer_chart_uri=(ASSETS / "charts" / "marketer.png").resolve().as_uri(),
        marketer_screen_uri=(ASSETS / "screenshots" / "02-marketer-result.png").resolve().as_uri(),
        persona_compare_uri=(ASSETS / "screenshots" / "04-persona-comparison.png").resolve().as_uri(),
        clarification_uri=(ASSETS / "screenshots" / "05-clarification.png").resolve().as_uri(),
    )
    HTML_OUT.write_text(html, encoding="utf-8")


def print_pdf(output: Path) -> None:
    with sync_playwright() as playwright:
        launch_kwargs = {"headless": True}
        if CHROME.exists():
            launch_kwargs["executable_path"] = str(CHROME)
        browser = playwright.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.goto(HTML_OUT.resolve().as_uri(), wait_until="networkidle")
        page.wait_for_function("document.fonts && document.fonts.status === 'loaded'")
        page.emulate_media(media="print", color_scheme="light", reduced_motion="reduce")
        page.pdf(
            path=output,
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()


def extract_text(pdf_path: Path) -> list[str]:
    with pdfplumber.open(pdf_path) as pdf:
        return [(page.extract_text() or "").strip() for page in pdf.pages]


def validate_pdf(pdf_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    texts = extract_text(pdf_path)
    if len(reader.pages) != 10 or len(texts) != 10:
        raise AssertionError(f"Expected 10 pages, got {len(reader.pages)} / {len(texts)}")
    too_short = [index + 1 for index, text in enumerate(texts) if len(text) < 120]
    if too_short:
        raise AssertionError(f"Pages with too little extractable text: {too_short}")
    full_text = "\n".join(texts)
    required = [
        "RoleLens",
        "SQL이 본업은 아닌",
        "LLM은 의미를",
        "질문에서 Insight Card까지",
        "PostgreSQL Mock 데이터",
        "20대 카테고리 매출",
        "같은 질문이어도",
        "76 / 76",
        "향후 확장 후보 - 현재 미구현",
        "동일한 Mock 환경",
        "RAG",
        "LangGraph",
        "Vector DB",
    ]
    missing = [item for item in required if item not in full_text]
    if missing:
        raise AssertionError(f"Missing required text: {missing}")
    forbidden = [
        r"sk-[A-Za-z0-9_-]{12,}",
        r"postgresql\+psycopg://[^\s]+:[^\s]+@",
        r"OPENAI_API_KEY\s*=\s*[^\s]+",
        r"MODEL_API_KEY\s*=\s*[^\s]+",
    ]
    leaks = [pattern for pattern in forbidden if re.search(pattern, full_text)]
    if leaks:
        raise AssertionError(f"Potential secret patterns found: {leaks}")
    return {
        "page_count": len(reader.pages),
        "file_size_bytes": pdf_path.stat().st_size,
        "page_text_lengths": [len(text) for text in texts],
        "text_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        "korean_extractable": "데이터" in full_text and "분석" in full_text,
        "mock_disclosure_present": "Mock" in full_text or "MOCK" in full_text,
        "future_tech_separated": "현재 미구현" in full_text,
        "secret_patterns_found": False,
    }


def render_pages() -> None:
    if RENDERED.exists():
        shutil.rmtree(RENDERED)
    RENDERED.mkdir(parents=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", "150", str(PDF_OUT), str(RENDERED / "page")],
        check=True,
    )


def main() -> None:
    require_inputs()
    TMP.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    analysis_svg = verify_and_export_diagram(DIAGRAMS / "analysis-flow.html")
    safety_svg = verify_and_export_diagram(DIAGRAMS / "sql-safety.html")
    data = write_report_data()
    render_html(data, analysis_svg, safety_svg)
    print_pdf(PDF_OUT)
    first = validate_pdf(PDF_OUT)
    print_pdf(STABILITY_PDF)
    second = validate_pdf(STABILITY_PDF)
    if first["page_count"] != second["page_count"] or first["text_sha256"] != second["text_sha256"]:
        raise AssertionError("Two-pass PDF build was not text/layout stable")
    render_pages()
    validation = {
        **first,
        "two_pass_stable": True,
        "rendered_png_count": len(list(RENDERED.glob("page-*.png"))),
        "output": str(PDF_OUT),
    }
    (VALIDATION / "pdf-validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    subprocess.run(["pdfinfo", str(PDF_OUT)], check=True)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
