# RoleLens 기술 설계

## 1. 설계 목표

- 노트북에서 핵심 흐름을 검증한 뒤 재사용 가능한 Python 모듈로 추출한다.
- PostgreSQL, LangChain 체인, 후처리, 시각화, Gradio UI의 책임을 분리한다.
- LLM의 비결정적 판단과 SQL/Python의 결정적 실행을 분리한다.
- 오류·모호함·위험 SQL을 명시적으로 다룬다.
- RAG·LangGraph·vector DB를 지금 구현하지 않되 이후 교체 가능한 경계를 유지한다.

## 2. 권장 기술 스택

- Python 3.11 이상
- LangChain과 수업에서 사용하는 LLM provider 패키지
- PostgreSQL 16 호환 환경, Docker Compose
- SQLAlchemy 2.x, psycopg 3, Alembic
- pydantic, pydantic-settings, python-dotenv
- pandas, matplotlib 또는 seaborn
- Gradio Blocks
- sqlglot 등 PostgreSQL AST를 검사할 수 있는 SQL parser
- pytest

모델은 `MODEL_PROVIDER`, `MODEL_ID` 설정으로 초기화한다. API 키와 DB 접속 문자열은 환경변수로 주입한다.

## 3. 전체 아키텍처

```text
Gradio Blocks
    |
    v
InsightService.run(AnalysisRequest)
    |
    +--> InputValidator
    |
    +--> Persona RunnableBranch
    |       └--> AnalysisPlan (Pydantic)
    |
    +--> clarification_needed? --> ClarificationResponse
    |
    +--> SQL Agent
    |       ├--> list_tables
    |       ├--> inspect_schema
    |       └--> execute_readonly_sql
    |
    +--> QueryArtifact
    |
    +--> Deterministic Result Analyzer
    |
    +--> Chart Planner --> Safe Chart Renderer
    |
    +--> Evidence-grounded Insight Writer
    |
    └--> AnalysisResponse(InsightCard, DataFrame, Figure, Trace)

PostgreSQL
    ├--> owner/migration/seed connection
    └--> agent read-only connection
```

UI, 노트북, 테스트는 모두 `InsightService.run()`과 같은 애플리케이션 진입점을 사용한다. DB와 LangChain 구현을 UI 이벤트 함수에 직접 넣지 않는다.

## 4. 프로젝트 구조

```text
rolelens/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── docker-compose.yml
├── alembic.ini
├── migrations/
├── notebooks/
│   └── 01_prototype.ipynb
├── scripts/
│   └── seed_mock_data.py
├── src/rolelens/
│   ├── __init__.py
│   ├── config.py
│   ├── domain/
│   │   ├── models.py
│   │   ├── metrics.py
│   │   └── personas.py
│   ├── db/
│   │   ├── engine.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── safety.py
│   ├── agents/
│   │   ├── prompts.py
│   │   ├── planner.py
│   │   ├── sql_agent.py
│   │   └── insight_writer.py
│   ├── services/
│   │   └── insight_service.py
│   ├── visualization/
│   │   ├── chart_planner.py
│   │   └── renderer.py
│   └── ui/
│       └── gradio_app.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/
```

RAG·LangGraph용 빈 폴더나 사용하지 않는 패키지는 만들지 않는다. 확장 시 현재 서비스 경계를 구현체 교체 지점으로 사용한다.

## 5. 핵심 데이터 타입

### 5.1 요청과 분석 계획

```python
class AnalysisRequest(BaseModel):
    persona: Literal["planner", "marketer", "pm"]
    question: str = Field(min_length=1, max_length=500)

class AnalysisPlan(BaseModel):
    persona: Literal["planner", "marketer", "pm"]
    interpreted_question: str
    metric: str
    dimensions: list[str]
    filters: list[str]
    date_range: str
    comparison: str | None
    chart_hint: ChartType
    clarification_needed: bool
    clarification_question: str | None
```

### 5.2 조회 결과

```python
class QueryArtifact(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict]
    source_tables: list[str]
    row_count: int
    data_as_of: date
    attempts: int
```

### 5.3 차트와 응답

```python
class ChartSpec(BaseModel):
    chart_type: ChartType
    x: str | None
    y: str | None
    series: str | None
    title: str
    x_label: str | None
    y_label: str | None
    sort: Literal["none", "ascending", "descending"] = "none"
    top_n: int | None = None

class AnalysisResponse(BaseModel):
    status: Literal["success", "clarification", "error"]
    insight: InsightCard | None
    query: QueryArtifact | None
    chart_spec: ChartSpec | None
    trace: list[TraceEvent]
    user_message: str | None
```

Figure와 DataFrame처럼 Pydantic 직렬화에 부적합한 UI 객체는 서비스 결과의 별도 런타임 필드나 표시 전용 DTO로 전달한다.

## 6. PostgreSQL 설계

### 6.1 스키마와 계정

- `analytics`: users, user_events, products, campaigns, orders, monthly_targets
- `rolelens_owner`: migration과 seed 전용
- `rolelens_agent_ro`: `analytics`의 허용 테이블에 대한 `SELECT` 전용

앱은 다음 URL을 분리한다.

```env
DATABASE_ADMIN_URL=postgresql+psycopg://...
DATABASE_READONLY_URL=postgresql+psycopg://...
```

- Alembic과 seed만 관리자 URL을 사용한다.
- 스키마 조회와 분석 SQL은 읽기 전용 URL만 사용한다.
- `search_path`를 `analytics`로 제한하더라도 생성 SQL에는 스키마를 명시하는 것을 권장한다.
- statement timeout과 connection timeout을 설정한다.

### 6.2 Mock 데이터 수명주기

1. Docker Compose로 PostgreSQL 시작
2. Alembic migration으로 테이블 생성
3. `scripts/seed_mock_data.py --seed 42` 실행
4. 기존 Mock 데이터를 명시적으로 비우거나 upsert해 중복 없이 재생성
5. 행 수·FK·기준 집계를 검증

생성된 DB 볼륨은 제출 ZIP에 포함하지 않는다.

## 7. SQL Agent와 Tool

### 7.1 `list_tables()`

- 코드에 정의된 allowlist와 DB metadata의 교집합만 반환한다.
- 시스템 스키마와 마이그레이션 테이블은 노출하지 않는다.

### 7.2 `inspect_schema(table_names)`

- 허용된 테이블의 컬럼, 타입, PK/FK, 업무 설명만 반환한다.
- 요청한 이름이 allowlist 밖이면 실패한다.

### 7.3 `execute_readonly_sql(sql)`

실행 전에 다음을 검증한다.

1. PostgreSQL dialect로 파싱 가능
2. 정확히 하나의 statement
3. 최종 문장이 `SELECT`인 조회 CTE 또는 `SELECT`
4. DDL·DML·COPY·CALL·권한 변경·잠금 명령 없음
5. `SELECT *` 없음
6. 참조 테이블이 allowlist 안에 있음
7. 시스템 카탈로그와 다른 스키마 참조 없음
8. 최대 반환 행과 timeout 적용

실행 실패 시 스택 트레이스를 모델에 그대로 노출하지 않고 오류 유형, 메시지, 허용 스키마 정보를 정제해 반환한다.

## 8. 결과 분석과 시각화

LLM에게 숫자 계산이나 임의 Python 코드 실행을 맡기지 않는다. 다음은 결정적 함수가 계산한다.

- 합계, 평균, 최대, 최소
- 순위와 구성비
- 이전 기간 대비 증감률
- 목표 대비 달성률
- 퍼널 전환율

ChartSpec은 허용 차트 목록과 실제 결과 컬럼을 기준으로 검증한다.

1. 차트 유형 확인
2. x/y/series 컬럼 존재 확인
3. 데이터 타입 확인
4. `top_n` 1~10 확인
5. 정렬·축·단위 적용
6. 안전한 렌더러로 Figure 생성

렌더링 실패 시 SQL을 재실행하지 않고 DataFrame과 시각화 실패 안내를 반환한다.

## 9. Gradio UI

### 9.1 입력

- 페르소나 Radio 또는 Dropdown
- 질문 Textbox
- 페르소나별 예시 질문
- 분석 실행 Button

### 9.2 출력

- 인사이트: headline, key findings, 후속 질문, 주의사항
- 시각화: Plot
- 데이터: Dataframe
- 근거: 적용 기준, 사용 테이블, SQL, 데이터 기준일
- 상태: 진행 단계와 사용자에게 안전한 오류 메시지

UI 이벤트는 입력을 `AnalysisRequest`로 변환하고 `InsightService.run()`을 한 번 호출한 뒤 결과를 표시하는 역할만 한다.

## 10. 오류 처리

| 오류 | 처리 |
|---|---|
| API 키 없음 | 실행 전 환경변수 설정 안내 |
| DB 미실행·접속 실패 | Docker Compose와 설정 확인 안내 |
| 지원하지 않는 페르소나 | 허용 값 안내 |
| 빈 질문 | 모델 호출 없이 입력 오류 |
| 모호한 질문 | SQL 호출 없이 확인 질문 |
| 위험 SQL | 실행 차단, 이유 기록 |
| SQL 문법·스키마 오류 | 최대 2회 수정 후 실패 응답 |
| SQL timeout | 재시도하지 않고 범위 축소 안내 |
| 빈 결과 | 조건에 해당하는 데이터 없음 표시 |
| ChartSpec 오류 | 안전한 기본 차트 또는 테이블 fallback |
| Structured Output 오류 | 제한된 재파싱 후 사용자 안전 오류 |

## 11. 관찰 가능성

다음 항목을 구조화 로그와 요청 trace에 남긴다.

- request ID와 처리 시간
- 선택된 페르소나 분기
- 구조화된 AnalysisPlan
- Tool 이름, 성공 여부, 소요 시간
- 생성·수정된 SQL과 시도 횟수
- QueryArtifact metadata
- ChartSpec
- 최종 상태

API 키, DB 비밀번호, 전체 프롬프트의 비밀값, 모델의 비공개 추론은 기록하지 않는다.

## 12. 설정과 패키징

`.env.example`에는 변수명과 안전한 예시만 제공한다.

Docker Compose 전용 로컬 개발 계정의 예시값은 제공할 수 있지만, 개인 API 키나 외부·운영 시스템의 실제 인증정보는 포함하지 않는다.

```env
MODEL_PROVIDER=
MODEL_ID=
MODEL_API_KEY=
DATABASE_ADMIN_URL=
DATABASE_READONLY_URL=
RANDOM_SEED=42
DATA_AS_OF=2026-09-15
SQL_STATEMENT_TIMEOUT_MS=10000
MAX_QUERY_ROWS=100
```

제출 전 ZIP에는 다음을 포함하지 않는다.

- `.env`, API 키, 실제 비밀번호
- `.venv`, `__pycache__`, `.pytest_cache`
- PostgreSQL volume, 로그, 임시 차트
- IDE 사용자 설정과 운영체제 메타데이터
