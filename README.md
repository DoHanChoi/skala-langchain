# RoleLens

RoleLens는 기획자·마케터·PM이 한국어로 데이터를 질문하고, 자신의 업무 관점에 맞는 인사이트를 받을 수 있는 학습용 데이터 분석 서비스입니다.

Mock 커머스 데이터와 PostgreSQL을 사용하며, 분석 결과를 인사이트·차트·원본 데이터·실행 SQL 형태로 함께 제공합니다.

## 핵심 기능

- **직무별 분석**: 같은 질문도 기획자는 목표·추이, 마케터는 채널·세그먼트, PM은 활성화·전환 관점으로 분석합니다.
- **자연어 데이터 질문**: 한국어 질문을 분석 계획과 PostgreSQL 조회로 변환합니다.
- **한눈에 보는 분석 결과**: 핵심 답변, 2~3개의 발견, 차트, 조회 데이터, 근거 SQL을 하나의 화면에서 확인합니다.
- **모호한 질문 확인**: 기간이나 기준이 불명확하면 임의로 조회하지 않고 구체적인 확인 질문을 반환합니다.
- **근거 기반 숫자**: 매출 증감률, 목표 달성률, 활성화율은 LLM이 아닌 결정적 Python 함수로 계산합니다.
- **안전한 조회**: 읽기 전용 DB 계정, SQL AST 검사, 테이블 allowlist, 행 수 제한, timeout으로 데이터를 보호합니다.
- **재현 가능한 데모**: Docker, Alembic, 고정 seed를 사용해 동일한 Mock 환경을 다시 만들 수 있습니다.

## 분석 흐름

```text
페르소나 선택 → 한국어 질문 → 분석 계획 → 안전한 SQL 조회
                 → Python 지표 계산 → 인사이트·차트·데이터·근거
```

## 예시 질문

- Planner: `이번 분기 매출이 목표 대비 어떤가?`
- Marketer: `최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.`
- PM: `최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.`

## 빠른 시작

### 준비물

- Python 3.11
- Docker Desktop / Docker Compose
- OpenAI API key

### 1. 설치

```bash
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

`.env`에 API key를 입력합니다.

```dotenv
MODEL_API_KEY=your-key
```

### 2. DB 준비

```bash
docker compose up -d --wait db
alembic upgrade head
python scripts/seed_mock_data.py --seed 42
```

### 3. 앱 실행

```bash
python -m rolelens.ui.gradio_app
```

터미널에 표시된 로컬 URL을 열면 Gradio 화면을 사용할 수 있습니다. API key가 없으면 서버를 시작하지 않고 `.env` 설정 방법을 안내합니다.

## 테스트

```bash
pytest
```

단위, PostgreSQL 통합, 표준 시나리오 E2E, SQL 안전성, read-only 권한을 검증합니다.

## 주요 구조

```text
notebooks/01_prototype.ipynb   # 핵심 기술 검증
src/rolelens/                 # 분석 파이프라인·DB·서비스·UI
sql/reference/                # 표준 시나리오 기준 SQL
migrations/                   # PostgreSQL 스키마와 권한
tests/                        # 단위·통합·E2E 테스트
docs/                         # 제품·기술·데이터 명세
```

## 범위와 제한

- 학습과 데모를 위한 Mock 데이터만 사용합니다.
- 현재 범위에는 RAG, LangGraph, vector DB, SQLite, React가 포함되지 않습니다.
- LLM은 질문 해석·SQL 초안·서술을 담당하며, 임의 Python 코드를 실행하지 않습니다.

상세 설계와 테스트 기준은 [`docs/README.md`](docs/README.md)에서 확인할 수 있습니다.
