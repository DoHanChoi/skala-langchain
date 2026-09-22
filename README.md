# RoleLens

RoleLens는 기획자·마케터·PM이 한국어로 데이터 질문을 입력하면, 공통 지표 정의와 선택한 직무의 분석 관점을 적용해 PostgreSQL을 조회하고 근거 있는 Insight Card를 제공하는 학습용 MVP입니다.

최종 애플리케이션은 Gradio Blocks UI이며, Jupyter Notebook은 핵심 기술 검증용입니다. Mock 데이터만 사용하며 RAG, LangGraph, vector DB, SQLite, FastAPI 애플리케이션 계층은 구현하지 않습니다. Gradio가 전이 의존성으로 FastAPI를 설치할 수는 있지만 RoleLens 코드가 FastAPI를 사용하지는 않습니다.

## 핵심 기능

- `planner`, `marketer`, `pm` 선택값을 `RunnableBranch`로 명시적 분기
- Pydantic `AnalysisPlan`, `QueryArtifact`, `ChartSpec`, `InsightCard`, `AnalysisResponse`
- PostgreSQL 16, Alembic migration, seed 42로 재생성하는 Mock 커머스 데이터
- SQL AST 검사, 테이블 allowlist, 100행 제한, statement timeout, DB read-only 계정
- SQL 오류 최대 2회 수정(초기 시도 포함 최대 3회)
- TS-01~03의 LLM SQL 핵심 결과를 수동 검토 기준 SQL과 대조하고, 2회 수정 후에도 틀리면 기준 SQL로 안전하게 대체
- 증감률·달성률·활성화율을 결정적 Python 함수로 계산
- 검증된 `ChartSpec`만 matplotlib 안전 렌더러로 시각화
- UI가 DB·LangChain을 직접 조립하지 않고 `InsightService.run()`만 호출

## 사전 준비

- Python 3.11 권장(검증 버전: 3.11.15)
- Docker Desktop과 Docker Compose
- OpenAI API key
- macOS, Linux 또는 Docker를 실행할 수 있는 환경

수업 예제와 동일하게 OpenAI를 사용하며 기본 모델은 `gpt-4o-mini`입니다. `MODEL_ID`로 변경할 수 있지만 Structured Outputs와 function calling을 지원하는 모델이어야 합니다.

## 1. 설치

```bash
cd rolelens
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

`.env`에 개인 API key를 추가합니다. 두 이름 중 하나를 사용하면 됩니다.

```dotenv
MODEL_API_KEY=your-key
# 또는 OPENAI_API_KEY=your-key
```

`.env`는 Git과 제출 ZIP에 포함하지 마세요. `.env.example`의 DB 비밀번호는 로컬 Docker 실습용 예시이며 외부·운영 DB에 사용하면 안 됩니다.

## 2. PostgreSQL, migration, seed

호스트의 기존 PostgreSQL `5432`와 충돌하지 않도록 기본 포트는 `55432`입니다.

```bash
docker compose up -d --wait db
docker compose ps
alembic upgrade head
python scripts/seed_mock_data.py --seed 42
```

기대 seed 행 수:

| 테이블 | 행 수 |
|---|---:|
| `analytics.users` | 1,200 |
| `analytics.user_events` | 5,203 |
| `analytics.products` | 25 |
| `analytics.campaigns` | 84 |
| `analytics.orders` | 3,907 |
| `analytics.monthly_targets` | 42 |

seed는 해당 6개 Mock 테이블을 FK 순서에 맞게 초기화하고 재생성 검증을 수행합니다. 운영 데이터와 혼용하지 마세요.

## 3. 테스트

```bash
pytest
```

현재 테스트 계층:

- 단위: 입력 계약, `RunnableBranch`, Structured Output 연결, 기간·지표 함수, SQL AST, 차트, UI 변환
- 통합: migration 후 seed 재실행, metadata Tool, 100행 제한, read-only DML 거부, timeout, 정답 SQL
- E2E: 세 표준 시나리오의 `InsightService → Gradio` 매핑

DB 없이 단위 테스트만 실행하려면:

```bash
pytest tests/unit
```

## 4. 프로토타입 Notebook

DB migration과 seed 후 `notebooks/01_prototype.ipynb`를 Python 3.11 커널로 엽니다. Notebook은 다음을 검증합니다.

1. `RunnableBranch`의 페르소나 분기
2. 동일한 Pydantic 계획 스키마
3. read-only PostgreSQL 정답 SQL
4. DataFrame과 결정적 목표 달성률 계산
5. 차트와 근거 요약
6. API key가 있을 때만 실행되는 선택적 live Structured Output smoke test

운영 로직은 Notebook에 두지 않고 `src/rolelens` 및 `InsightService`로 추출했습니다.

## 5. Gradio UI 실행

```bash
python -m rolelens.ui.gradio_app
```

터미널에 표시된 로컬 URL을 엽니다. UI는 다음 영역을 제공합니다.

- 입력: 페르소나, 페르소나별 예시 질문, 자연어 질문, 분석 버튼
- 인사이트: 핵심 답변, 2~3개 발견, 후속 질문, 주의사항
- 시각화: 검증된 `ChartSpec` 기반 차트 1개
- 데이터: 조회 결과 표
- 근거: 기간·필터·지표, 테이블, 행 수, 기준일, 최종 SQL

API key가 없으면 앱은 시작하지 않고 `.env` 생성과 key 설정 방법을 안내합니다.

## 표준 시나리오

1. Planner: `이번 분기 매출이 목표 대비 어떤가?`
2. Marketer: `최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.`
3. PM: `최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.`
4. 공통 비교: `최근 신규 고객 수가 어떻게 변했어?`
5. 모호함: `요즘 잘 나가는 상품을 보여줘.`

seed 42 기준의 정답 SQL은 `sql/reference/` 아래에 있으며, 최초 3개 시나리오의 핵심 기준값은 다음과 같습니다.

- 2026년 3분기 월별 매출 목표 달성률: 95.69%
- 최근 3개월 20대 beauty 매출: 9,224,188.55 KRW
- 7일 활성화율: mobile 43.06%, desktop 61.70%, tablet 66.67%

## 안전 경계

SQL은 실행 전에 `sqlglot` PostgreSQL AST로 다음을 검사합니다.

- 하나의 `SELECT` 또는 `WITH ... SELECT`만 허용
- `SELECT *`, DDL, DML, COPY, 권한 변경, lock, 다중 statement 차단
- `analytics` 스키마의 6개 테이블만 허용
- `information_schema`, `pg_catalog`, `public`, Alembic 테이블 접근 차단
- 최대 100행과 10초 statement timeout
- `rolelens_agent_ro`는 DB에서도 read-only 트랜잭션과 `SELECT` 권한만 사용

LLM은 SQL 초안·질문 해석·서술을 담당하지만 숫자 계산과 차트 Python 코드를 임의로 실행하지 않습니다.

## 프로젝트 구조

```text
rolelens/
├── docker-compose.yml
├── migrations/                 # Alembic schema and grants
├── notebooks/01_prototype.ipynb
├── scripts/seed_mock_data.py
├── sql/reference/              # reviewed acceptance SQL
├── src/rolelens/
│   ├── domain/                  # Pydantic contracts, metrics, periods
│   ├── db/                      # models, AST safety, repository, tools
│   ├── agents/                  # prompts, branch, SQL agent, writer
│   ├── visualization/           # ChartSpec planning and renderer
│   ├── services/insight_service.py
│   └── ui/gradio_app.py
├── tests/{unit,integration,e2e}/
└── docs/
```

## 사용 버전

Python 3.11에서 다음 핵심 버전을 검증했습니다.

| 패키지 | 버전 |
|---|---:|
| `langchain-core` | 1.6.3 |
| `langchain-openai` | 1.6.2 |
| `gradio` | 6.28.0 |
| `SQLAlchemy` | 2.0.54 |
| `psycopg` | 3.3.6 |
| `alembic` | 1.20.0 |
| `sqlglot` | 28.10.1 |
| `pydantic` | 2.13.5 |
| `pandas` | 3.0.6 |
| `matplotlib` | 3.11.2 |
| `pytest` | 9.1.1 |
| `nbclient` | 0.11.0 |

`langchain` 메타패키지는 현재 LangGraph를 전이 의존성으로 설치하므로 제외했습니다. RoleLens에 필요한 LCEL, `RunnableBranch`, Tool, prompt, structured output은 `langchain-core` 및 `langchain-openai`로 구성합니다.

## 문제 해결

- Docker socket 오류: Docker Desktop을 실행한 후 `docker info`를 확인하세요.
- `55432` 포트 충돌: `.env`의 `POSTGRES_HOST_PORT`와 두 DB URL의 포트를 함께 바꾸세요.
- migration 전 seed 오류: `alembic upgrade head`를 먼저 실행하세요.
- API key 오류: `.env`의 `MODEL_API_KEY` 또는 `OPENAI_API_KEY`를 확인하세요.
- 한글 폰트: AppleGothic, NanumGothic, Noto Sans CJK KR, Malgun Gothic 순으로 찾고 없으면 matplotlib 기본 폰트를 사용합니다.

## DB 종료·초기화

```bash
docker compose down
```

Mock DB 볼륨까지 삭제하고 처음부터 재검증하려면:

```bash
docker compose down -v
docker compose up -d --wait db
alembic upgrade head
python scripts/seed_mock_data.py --seed 42
pytest
```

## 문서

제품·데이터·아키텍처·프롬프트·테스트 명세는 [`docs/README.md`](docs/README.md), 현재 환경에 맞춘 선택과 차이는 [`docs/10_IMPLEMENTATION_NOTES.md`](docs/10_IMPLEMENTATION_NOTES.md)를 참고하세요.
