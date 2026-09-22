# RoleLens Product Requirements Document

## 1. 문서 정보

- 제품명: RoleLens
- 버전: MVP 1.0
- 제품 형식: Gradio Blocks 기반 로컬 웹 애플리케이션
- 제출 형식: 실행 가능한 프로젝트 ZIP
- DB: Docker Compose 기반 PostgreSQL
- 대상 페르소나: 기획자, 마케터, PM
- 핵심 기능: 직무와 자연어 질문을 입력받아 역할 맞춤형 Insight Card 생성

## 2. 목표

### 2.1 사용자 목표

- SQL을 직접 작성하지 않고 업무 질문에 대한 데이터 근거를 얻는다.
- 원시 테이블보다 핵심 수치와 차트를 먼저 확인한다.
- 직무에 맞는 비교 관점과 후속 분석 질문을 얻는다.
- 결과에 사용된 지표 정의, 필터, SQL, 데이터 기준일을 확인한다.

### 2.2 학습·구현 목표

- `입력 → 컨텍스트 구성 → 체인/에이전트 → DB Tool → 후처리 → UI 출력`을 하나의 흐름으로 구현한다.
- 공통 프롬프트와 페르소나 프롬프트를 분리한다.
- `RunnableBranch`, Pydantic Structured Output, SQL Tool/Agent, Output Parser를 목적에 맞게 사용한다.
- 노트북에서 핵심 기술을 먼저 검증하고 검증된 로직을 테스트 가능한 Python 모듈로 추출한다.

## 3. 범위

### 3.1 MVP 포함

- 3개 명시적 페르소나: `planner`, `marketer`, `pm`
- 한국어 자연어 분석 질문
- 구조화된 `AnalysisPlan`
- 결과에 큰 영향을 주는 모호함에 대한 확인 질문
- PostgreSQL Mock DB 스키마 탐색
- 조회 전용 SQL 생성·검증·실행
- SQL 결과의 `QueryArtifact`·DataFrame 변환
- 증감률·구성비·순위·달성률 등 결정적 Python 후처리
- 분석 목적에 맞는 차트 1개
- 구조화된 Insight Card
- SQL, 사용 테이블, 적용 필터, 지표 정의, 데이터 기준일
- SQL 문법·스키마 오류 최대 2회 수정
- Gradio Blocks 분석 UI
- Docker Compose PostgreSQL, DB 마이그레이션, 고정 seed Mock 데이터
- 단위·PostgreSQL 통합·서비스 흐름 테스트
- 핵심 기술 검증용 `notebooks/01_prototype.ipynb`

### 3.2 MVP 제외

- SQLite 및 운영 DB 연결
- 데이터 삽입·수정·삭제 UI
- 인증, 사용자별 권한, 멀티테넌시
- RAG, 문서 로더, embedding, vector DB, pgvector
- LangGraph, 장기 대화 메모리, 체크포인트
- FastAPI·React 분리와 클라우드 배포
- 외부 시각화 API
- 수요·매출 예측과 인과 추론
- 캠페인 실행·예산 배분 등 외부 시스템 변경

## 4. 사용자 스토리

### US-01 페르소나 선택

> 사용자는 직무를 선택해 질문이 해당 직무의 관점으로 분석되길 원한다.

인수 조건:

- UI에서 `planner`, `marketer`, `pm` 중 하나를 선택한다.
- 선택값은 `RunnableBranch`의 분기 조건으로 사용한다.
- 자동 페르소나 판정은 사용하지 않는다.

### US-02 자연어 분석 질문

> 비IT 직군 사용자는 SQL 대신 일상적인 업무 언어로 질문하고 싶다.

인수 조건:

- 질문을 지표, 차원, 필터, 기간, 비교 기준으로 구조화한다.
- 임의 가정이 결과를 크게 바꾸면 SQL 실행 전 확인 질문 하나를 반환한다.
- 공백을 제외한 질문의 권장 길이는 10~500자다.

### US-03 안전한 SQL 실행

> 사용자는 에이전트가 데이터를 변경하지 않고 허용된 분석 데이터만 조회하길 원한다.

인수 조건:

- SQL AST 검사로 단일 `SELECT` 또는 `WITH ... SELECT`만 허용한다.
- `analytics` 스키마의 allowlist 테이블만 조회한다.
- `SELECT *`, 다중 statement, DDL, DML, 시스템 카탈로그 조회를 차단한다.
- 에이전트는 `SELECT` 권한만 있는 DB 계정을 사용한다.
- 기본 최대 반환 행은 100개이며 statement timeout을 적용한다.
- 오류 수정은 최대 2회이며 최종 SQL을 근거 탭에 표시한다.

### US-04 Insight Card

> 사용자는 원시 테이블보다 핵심 답변과 차트를 먼저 보고 싶다.

인수 조건:

- 핵심 답변 1문장, 근거 기반 주요 발견 2~3개, 차트 1개를 제공한다.
- 적용 기간, 필터, 지표 정의, 비교 기준을 표시한다.
- 후속 분석 질문 1개를 제안한다.
- 사용 테이블, SQL, 조회 행 수, 데이터 기준일을 표시한다.
- 숫자 주장은 SQL 결과 또는 Python 통계에서 검증 가능해야 한다.

### US-05 Gradio 분석 화면

> 사용자는 한 화면에서 질문하고 인사이트, 차트, 데이터, SQL 근거를 확인하고 싶다.

인수 조건:

- 페르소나 선택, 예시 질문, 질문 입력, 분석 버튼을 제공한다.
- 결과는 `인사이트`, `시각화`, `데이터`, `근거` 영역으로 구분한다.
- 확인 질문과 오류는 사용자가 해결 방법을 알 수 있는 문장으로 표시한다.
- 채팅 기록과 대화 메모리는 제공하지 않는다.

### US-06 재현 가능한 프로젝트 실행

> 평가자·개발자는 ZIP을 풀고 안내된 순서로 같은 Mock 데이터와 표준 결과를 확인하고 싶다.

인수 조건:

- `.env.example`, `docker-compose.yml`, 의존성 명세, 마이그레이션, seed 스크립트, 실행 README를 포함한다.
- `RANDOM_SEED=42`로 재생성하면 동일한 행 수와 기준 집계를 얻는다.
- API 키와 실제 비밀번호를 ZIP에 포함하지 않는다.

## 5. 기능 요구사항

| ID | 요구사항 | 우선순위 |
|---|---|---:|
| FR-01 | 페르소나와 질문을 입력받는다. | Must |
| FR-02 | `RunnableBranch`로 페르소나 분석 체인을 선택한다. | Must |
| FR-03 | Pydantic Structured Output으로 `AnalysisPlan`을 반환한다. | Must |
| FR-04 | Tool로 DB 테이블·스키마를 확인한다. | Must |
| FR-05 | SQL을 AST·allowlist·DB 권한으로 검증한다. | Must |
| FR-06 | SQL 결과를 `QueryArtifact`와 DataFrame으로 보존한다. | Must |
| FR-07 | 숫자 후처리를 결정적 Python 함수로 수행한다. | Must |
| FR-08 | 검증된 `ChartSpec`에 따라 차트 1개를 렌더링한다. | Must |
| FR-09 | 결과를 `InsightCard`로 구조화한다. | Must |
| FR-10 | Gradio에서 인사이트·차트·테이블·근거를 표시한다. | Must |
| FR-11 | 모호한 질문에는 SQL 대신 확인 질문을 반환한다. | Should |
| FR-12 | SQL 오류를 최대 2회 수정한다. | Should |
| FR-13 | 페르소나·AnalysisPlan·Tool 실행·SQL·ChartSpec을 구조화 로그로 남긴다. | Should |

## 6. 비기능 요구사항

| ID | 요구사항 |
|---|---|
| NFR-01 | 새 환경에서 README를 따라 PostgreSQL, seed, 앱을 실행할 수 있어야 한다. |
| NFR-02 | Mock 데이터는 고정 seed로 재생성 가능해야 한다. |
| NFR-03 | API 키와 DB 비밀번호를 소스·노트북·ZIP에 하드코딩하지 않아야 한다. |
| NFR-04 | 평소 SQL은 10초 이내, 전체 분석은 정상 API 환경에서 60초 이내 종료를 목표로 한다. |
| NFR-05 | SQL 실행이 실패해도 Gradio 프로세스가 종료되지 않아야 한다. |
| NFR-06 | UI는 서비스 계층을 통해서만 분석 로직을 호출해야 한다. |
| NFR-07 | DB 조회에 읽기 전용 계정·statement timeout·테이블 allowlist를 적용해야 한다. |
| NFR-08 | `pytest`로 단위 테스트와 PostgreSQL 통합 테스트를 실행할 수 있어야 한다. |

## 7. 입력 계약

```python
class AnalysisRequest(BaseModel):
    persona: Literal["planner", "marketer", "pm"]
    question: str = Field(min_length=1, max_length=500)
```

- 공백만 있는 질문은 거부한다.
- SQL·Python 코드 자체를 질문으로 실행하는 시나리오는 범위 밖이다.
- 각 요청은 대화 기록과 독립적으로 처리한다.

## 8. 출력 계약

```python
class InsightCard(BaseModel):
    persona: Literal["planner", "marketer", "pm"]
    question: str
    headline: str
    key_findings: list[str]
    chart_spec: ChartSpec
    applied_context: list[str]
    next_analysis_question: str
    caveats: list[str]
    sql: str
    source_tables: list[str]
    row_count: int
    data_as_of: date
```

UI 표시 영역:

1. 인사이트: 페르소나, 질문, 핵심 답변, 주요 발견, 후속 질문
2. 시각화: 검증된 ChartSpec으로 생성한 차트
3. 데이터: 조회 결과 상위 행과 전체 조회 행 수
4. 근거: 적용 기준, SQL, 사용 테이블, 데이터 기준일

## 9. 시각화 규칙

허용 차트는 `bar`, `horizontal_bar`, `grouped_bar`, `stacked_bar`, `line`, `scatter`, `kpi`다.

- 범주 1개 + 수치 1개: `bar`
- 긴 범주명 + 수치: `horizontal_bar`
- 시간 + 수치: `line`
- 범주 + 비교 기간 + 수치: `grouped_bar`
- 범주 + 구성 집단 + 수치: `stacked_bar`
- 수치 2개: `scatter`
- 단일 지표: `kpi`

원그래프는 사용하지 않는다. 범주가 10개를 넘으면 상위 10개로 제한하고 이 사실을 표시한다.

## 10. 성공 기준

- 표준 질문 3개의 SQL·후처리·차트·Insight Card 생성 성공률 100%
- 위험 SQL 테스트 차단률 100%
- 최종 숫자 주장의 SQL 결과 일치율 100%
- 3개 페르소나 모두 선택·실행 가능
- 같은 질문에서 페르소나별 `AnalysisPlan` 차이가 확인됨
- 새 환경에서 PostgreSQL 초기화, seed, 테스트, Gradio UI 실행 성공

## 11. Definition of Done

- [ ] ZIP에 소스, 프로토타입 노트북, 문서, 테스트, Docker Compose, 의존성 명세, `.env.example`이 포함되었다.
- [ ] README의 명령으로 PostgreSQL, migration, seed, Gradio UI를 실행할 수 있다.
- [ ] 3개 표준 시나리오와 페르소나 공통 질문이 작동한다.
- [ ] SQL 안전, 모호함, 빈 결과, 차트 fallback을 테스트했다.
- [ ] 숫자 요약의 근거 대조가 완료되었다.
- [ ] API 키, 실제 `.env`, 비밀번호, DB 볼륨, 캐시가 ZIP에 없다.
- [ ] RAG, LangGraph, vector DB는 현재 의존성과 실행 경로에 포함되지 않았다.
