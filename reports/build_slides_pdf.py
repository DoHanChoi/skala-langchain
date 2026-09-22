from __future__ import annotations

import os
from pathlib import Path

from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SLIDES_DIR = Path(
    os.environ.get(
        "ROLELENS_SLIDE_RENDER_DIR",
        ROOT / "tmp" / "presentations" / "rolelens-slides" / "rendered-final",
    )
)
OUTPUT = ROOT / "output" / "pdf" / "RoleLens_서비스보고서_슬라이드.pdf"
PAGE_SIZE = (960.0, 540.0)


def main() -> None:
    slides = sorted(SLIDES_DIR.glob("slide-*.png"))
    if len(slides) != 7:
        raise RuntimeError(f"Expected 7 rendered slides, found {len(slides)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=PAGE_SIZE, pageCompression=1)
    pdf.setTitle("RoleLens 서비스보고서 - 슬라이드")
    pdf.setAuthor("RoleLens")
    pdf.setSubject("핵심 구조와 실제 실행 결과")
    for slide in slides:
        pdf.drawImage(str(slide), 0, 0, width=PAGE_SIZE[0], height=PAGE_SIZE[1])
        pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    main()
