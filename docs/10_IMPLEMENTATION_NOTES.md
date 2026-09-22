# RoleLens 구현 결정·검증 기록

## 1. 기준

- 구현일: 2026-09-21
- Phase 0~8 재검증일: 2026-09-22
- 문서 우선순위: PRD → 데이터·지표 명세 → 안전·아키텍처 제약 → 프롬프트 명세
- Python: 3.11.15
- PostgreSQL: Docker `postgres:16-alpine`, host port 55432
- 기본 provider/model: OpenAI / `gpt-4o-mini`

## 2. 구현 전 환경 점검

- 기본 `python3`는 3.14.7이지만 수업 Notebook의 Python 3.11 커널과 재현성을 맞추기 위해 3.11.15 가상환경을 사용했다.
- 수업 Notebook은 `langchain`, `langchain-openai`를 버전 고정 없이 설치하므로 정확한 수업 버전은 복원할 수 없었다. API 형태는 LangChain 1.x의 `init_chat_model`, `RunnableBranch`, `create_agent`, Structured Output을 사용한다.
- 전역 환경에는 LangChain, Gradio, Pydantic, psycopg, Alembic, pytest가 설치되어 있지 않았다.
- Docker CLI·Compose·Docker Desktop은 설치되어 있었지만 daemon은 꺼져 있었다.
- host 5432는 다른 PostgreSQL 프로세스가 점유하고 있어 55432를 선택했다.
- 초기 점검 시 `MODEL_API_KEY`, `OPENAI_API_KEY` 환경변수는 없었다. 구현 후 사용자가 임시로 제공한 `MODEL_API_KEY`로 live model과 전체 서비스를 검증했고, 키 값은 제출물에서 제거했다.

## 3. 문서 대비 선택·차이

### `langchain` 메타패키지 제외

2026-09-21의 `langchain==1.4.2`를 설치하면 `langgraph` 1.2.x가 직접 의존성으로 설치된다. PRD와 향후 확장 문서는 현재 MVP 의존성에서 LangGraph를 제외하라고 명시한다. 따라서 다음 구성으로 대체했다.

- `langchain-core==1.6.3`: `RunnableBranch`, LCEL, prompt, Tool
- `langchain-openai==1.6.2`: `ChatOpenAI`, Pydantic Structured Output
- `langchain` 메타패키지·`langgraph` 미설치

제품 요구인 명시적 분기·Tool·Structured Output은 그대로 유지된다.

### API key 이름

설계 문서는 `MODEL_API_KEY`, 수업 예제는 `OPENAI_API_KEY`를 사용한다. 설정 모델은 둘 다 읽고 `MODEL_API_KEY`를 우선하며, 소스·Notebook·로그에 값을 출력하지 않는다.

### SQL 행 제한

SQL 문자열을 바꾸는 대신 sqlglot AST에 `LIMIT 100`을 적용한다. 이미 더 작은 고정 LIMIT이 있으면 유지하고, 표현식 LIMIT은 거부한다.

### 목표 비교 결과 계약

실행 가능한 SQL이라도 분기 전체 매출을 한 달의 목표와 비교하면 의미적으로 틀린 결과다. 라이브 브라우저 QA에서 이 케이스를 발견한 후, 월별 매출 목표 비교에 `month`, `actual_revenue`, `target_revenue`, `achievement_rate` 결과 계약을 적용했다. 계약을 만족하지 못한 SQL은 성공으로 채택하지 않고 최대 2회 수정한다.

### 정답 SQL 경로와 live 결과 대조

표준 시나리오의 수동 검토 SQL은 `sql/reference/` 아래에 두었다. seed 패턴, PostgreSQL 통합 테스트, API 없는 인수 테스트가 같은 SQL을 사용한다. live 애플리케이션은 LLM SQL Agent를 사용한다.

TS-01~03은 LLM이 생성한 SQL의 결과 형태와 핵심 값을 기준 SQL 결과와 대조한다. 불일치하면 최대 2회 수정하고, 그래도 불일치하면 검토된 기준 SQL 결과를 반환한다. 이 대체 경로도 같은 AST 검사·read-only Tool·timeout 경계를 거친다.

### 앱 시작 시 API key

CLI로 Gradio를 시작할 때 key가 없으면 서버를 열지 않고 `.env`를 생성하여 `MODEL_API_KEY` 또는 `OPENAI_API_KEY`를 설정하라는 오류를 반환한다. 테스트에서는 명시적인 `offline_acceptance_mode=True`에서만 검토된 SQL과 규칙 기반 계획을 사용한다.

## 4. Phase 결과

| Phase | 결과 |
|---|---|
| 0 | Python 3.11 venv, 패키지 import, Docker/Compose, PostgreSQL 연결 확인 |
| 1 | 6개 테이블, owner/read-only 역할, migration, seed, 정답 SQL, DML 거부 |
| 2 | Notebook의 branch → plan → SQL → DataFrame → chart → summary 실행 |
| 3 | 도메인 계약, 지표·기간, repository, DB Tool, AST 검사 추출 |
| 4 | 공통/페르소나 prompt, `RunnableBranch`, AnalysisPlan, clarification gate, SQL repair |
| 5 | DataFrame 변환, 결정적 계산, ChartSpec, renderer, 근거 작성 |
| 6 | `InsightService.run()` success/clarification/error, 의존성 주입, trace |
| 7 | Gradio Blocks의 인사이트·시각화·데이터·근거 영역 |
| 8 | README, 자동 테스트, 브라우저 QA, ZIP 검사 |

## 5. 검증된 기준값

seed 42:

- `users=1200`, `user_events=5203`, `products=25`, `campaigns=84`, `orders=3907`, `monthly_targets=42`
- completed orders 3,606건, cancelled/refunded 301건
- order date 2025-01-09 ~ 2026-09-15
- 2026년 3분기 월별 매출 목표 달성률 95.69%
- 최근 3개월 20대 beauty 매출 9,224,188.55 KRW
- 7일 활성화율: mobile 43.06%, desktop 61.70%, tablet 66.67%

## 6. 남은 한계

- OpenAI `gpt-4o-mini` 단순 호출, 공통 질문의 세 페르소나 AnalysisPlan 분기, Gradio에서 TS-01~03·clarification·입력 오류·오류 후 복구를 실제 모델로 검증했다.
- Gradio TS-01은 실제 매출 86,189,441.91원, 목표 90,067,966.80원, 달성률 95.69%로 기준 SQL과 일치했다. TS-02와 TS-03도 문서의 기준값과 일치했다.
- 자동 테스트는 fake/structured stub과 수동 검토 정답 SQL로 LLM 경계를 재현한다. 외부 API의 계정별 비용·장기 지연·일시적 장애는 별도 운영 관찰이 필요하다.
- Mock 데이터의 패턴은 학습·인수 검증용이며 실제 시장·고객 현상을 대표하지 않는다.
- 데이터 소스·지표·테이블이 바뀌면 정답 SQL과 통합 테스트를 함께 갱신해야 한다.

RAG, LangGraph, vector DB, pgvector는 현재 코드·의존성·Docker 경로에 없다.
