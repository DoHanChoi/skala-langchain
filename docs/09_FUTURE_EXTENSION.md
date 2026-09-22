# RoleLens 향후 확장 설계

## 1. 문서 목적

이 문서는 현재 MVP에 구현하지 않는 RAG, LangGraph, vector DB의 확장 방향을 기록한다. 현재 `pyproject.toml`, Docker Compose, 실행 경로에는 관련 패키지·서비스를 추가하지 않는다.

확장의 원칙은 “미리 구현”이 아니라 “현재 책임 경계를 유지해 나중에 구현체를 교체할 수 있게 하는 것”이다.

## 2. 현재 MVP 경계

```text
Gradio UI
  → InsightService
      → Persona Analysis Chain
      → SQL Agent + DB Tools
      → Result Analyzer
      → Chart Renderer
      → Insight Writer
  → PostgreSQL analytics schema
```

확장 시에도 UI 입력과 `AnalysisResponse` 계약은 가능한 한 유지한다.

## 3. RAG 확장

### 3.1 도입 목적

운영 데이터베이스의 의미는 테이블·컬럼 이름만으로 충분하지 않다. RAG는 SQL 결과 행을 검색하는 용도보다 다음 의미 컨텍스트를 제공하는 용도로 사용한다.

- 업무 용어집과 약어
- 테이블·컬럼의 업무 설명
- KPI·지표 정의와 변경 이력
- 검증된 자연어 질문 ↔ SQL 예시
- 데이터 품질·접근 정책
- 조직별 분석 가이드

원시 주문·이벤트 행 전체를 기본 RAG 문서로 임베딩하지 않는다. 정형 집계는 SQL이 담당한다.

### 3.2 삽입 지점

```text
AnalysisRequest
  → SemanticContextProvider.retrieve(question, persona)
  → AnalysisPlan
  → SQL Agent
```

현재 MVP에서는 `StaticSemanticContextProvider`가 코드의 지표 사전과 스키마 설명을 반환하는 형태로 시작할 수 있다. RAG 도입 시 동일한 인터페이스의 검색 구현체로 교체한다.

### 3.3 검증 기준

- 검색 컨텍스트가 없을 때보다 SQL 정확도가 좋아지는가?
- 잘못된 문서가 SQL을 오염시키지 않는가?
- 어떤 문서가 어떤 SQL 판단에 사용되었는지 추적 가능한가?
- 지표 정의 충돌 시 권위 있는 문서를 우선하는가?

## 4. vector DB 확장

초기 후보는 PostgreSQL과 함께 운영할 수 있는 pgvector다. 다만 다음 조건을 확인한 뒤 도입한다.

- 검색할 의미 문서와 평가셋이 준비됨
- 키워드 검색만으로 부족함이 확인됨
- embedding 모델과 갱신 정책이 결정됨
- metadata filter와 권한 필터 요구사항이 정리됨

도입 시 `analytics`와 분리된 `semantic` 스키마를 고려한다.

```text
semantic.documents
semantic.document_chunks
semantic.metric_definitions
semantic.verified_queries
```

검색 저장소는 `SemanticContextProvider` 뒤에 숨겨 향후 외부 vector DB로 바꾸더라도 분석 체인과 UI를 수정하지 않게 한다.

## 5. LangGraph 확장

### 5.1 도입 시점

현재의 선형 체인으로 다음 요구를 다루기 어려워질 때 도입한다.

- 사용자 확인 질문 후 같은 작업 재개
- SQL 검증 실패 유형별 조건부 재시도
- 실행 계획 승인 단계
- 여러 분석 쿼리의 병렬·순차 조합
- 장기 실행 상태와 체크포인트
- 사용자별 분석 세션

단순히 기술을 사용하기 위해 선형 MVP를 LangGraph로 옮기지 않는다.

### 5.2 예상 State

```python
class RoleLensState(TypedDict):
    request: AnalysisRequest
    semantic_context: list[ContextItem]
    analysis_plan: AnalysisPlan | None
    clarification: str | None
    sql: str | None
    query_artifact: QueryArtifact | None
    computed_metrics: dict
    chart_spec: ChartSpec | None
    insight: InsightCard | None
    attempts: int
    errors: list[WorkflowError]
```

### 5.3 예상 Node와 Edge

```text
route_persona
  → retrieve_semantics
  → plan_analysis
  → needs_clarification?
      ├─ yes → ask_user → resume
      └─ no  → generate_sql
                → validate_sql
                    ├─ invalid/retryable → repair_sql
                    ├─ blocked → fail_safely
                    └─ valid → execute_sql
                                → analyze_result
                                → plan_chart
                                → write_insight
```

LangGraph 도입 후에도 기존 `InsightService`가 WorkflowEngine을 호출하도록 하여 Gradio UI를 유지한다.

## 6. 저장소 확장

장기 상태가 필요해지면 PostgreSQL을 다음처럼 분리할 수 있다.

- `analytics`: 분석 대상 Mock 또는 업무 데이터
- `semantic`: RAG 문서와 embedding
- `agent`: 세션, checkpoint, 실행 trace

분석용 read-only 계정과 agent 상태 저장 계정은 분리한다. SQL Agent가 `semantic` 또는 `agent` 스키마를 직접 조회하게 하지 않는다.

## 7. FastAPI와 UI 확장

다음 요구가 생기면 InsightService 앞에 FastAPI를 추가한다.

- Gradio 외의 클라이언트
- 비동기 작업과 작업 상태 API
- 인증과 사용자별 권한
- 독립 배포와 모니터링

```text
Gradio / Web Client
  → FastAPI
      → InsightService
          → WorkflowEngine
```

현재 MVP에서 FastAPI를 추가하지 않는 이유는 단일 로컬 UI에 중복 계층과 배포 복잡도를 만들기 때문이다.

## 8. 확장 전 평가 항목

새 기술을 도입하기 전에 다음을 먼저 준비한다.

- 대표 질문과 정답 SQL 평가셋
- 지표 정의 충돌 사례
- 모호한 질문과 확인 질문 평가셋
- SQL 생성 성공률·수정률·차단률
- 검색 정확도와 출처 추적 지표
- 응답 시간과 LLM 호출 비용

평가 결과로 현재 체인의 한계가 확인된 경우에만 해당 확장을 시작한다.

## 9. 현재 MVP에서 지킬 사항

- RAG·LangGraph·vector DB 패키지를 설치하지 않는다.
- pgvector extension과 별도 vector DB 컨테이너를 생성하지 않는다.
- 미래 기능을 위한 빈 화면과 비활성 버튼을 만들지 않는다.
- 인터페이스를 과도하게 일반화하지 않는다.
- 현재 필요한 `InsightService`, DB repository, 렌더러의 책임을 분리하는 수준으로만 확장성을 확보한다.
