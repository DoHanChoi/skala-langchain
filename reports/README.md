# RoleLens 서비스 보고서

최종 채택본은 16:9 슬라이드형 PDF와 PPTX다. 실제 PostgreSQL Mock seed, RoleLens 서비스 출력, Gradio UI 캡처, 실행 검증 결과를 7장으로 정리한다.

## 필요 환경

- Python 3.11 가상환경
- Docker Desktop / Docker Compose
- Google Chrome 또는 Playwright Chromium
- Poppler (`pdftoppm`, `pdfinfo`)
- 프로젝트 의존성과 `.[report]` extra

```bash
source .venv/bin/activate
pip install -e ".[dev,report]"
docker compose up -d --wait db
alembic upgrade head
python scripts/seed_mock_data.py --seed 42
```

## 근거 데이터 갱신

```bash
python reports/collect_evidence.py
python reports/run_live_smoke.py  # 선택: API 키·네트워크 필요
python reports/capture_report_assets.py
```

앱 캡처는 외부 API 변동을 피하기 위해 실제 DB와 검토된 reference SQL을 쓰는 `offline_acceptance_mode=True`로 실행한다. Live LLM smoke test 결과는 별도로 구분한다.

## 산출물

- 실행 근거: `reports/evidence/`
- 실제 UI 캡처: `reports/assets/screenshots/`
- 결정론적 차트: `reports/assets/charts/`
- 다이어그램 HTML/SVG/PNG: `reports/assets/diagrams/`
- 편집용 PPTX: `output/pptx/RoleLens_서비스보고서_슬라이드.pptx`
- 발표용 PDF: `output/pdf/RoleLens_서비스보고서_슬라이드.pdf`

## 다이어그램 갱신

`reports/assets/diagrams/*.html`의 inline SVG를 수정한 뒤 SVG와 슬라이드용 PNG를 같이 갱신한다.

## 오프라인 제약

슬라이드는 `Nanum Gothic`을 사용한다. Live LLM 재검증은 `MODEL_API_KEY` 또는 `OPENAI_API_KEY`와 네트워크가 필요하지만, 인수 시나리오 재현은 API 호출 없이 가능하다.
