# RoleLens 프롬프트·체인 명세

## 1. 설계 원칙

- 공통 안전 규칙, 공통 지표 정의, 페르소나 관점을 분리한다.
- 페르소나는 지표의 의미를 바꾸지 않고 분석 초점을 바꾼다.
- LLM은 질문 해석, SQL 작성, 차트 계획, 서술을 담당한다.
- SQL과 Python은 조회와 숫자 계산을 담당한다.
- 요약은 원문 질문, 실행 결과, 결정적 계산 밖의 사실을 사용하지 않는다.
- 현재 MVP는 단일 요청 단위 체인이며 대화 메모리, RAG, LangGraph를 사용하지 않는다.

## 2. 전체 체인

```text
AnalysisRequest
  → validate_input
  → persona RunnableBranch
  → AnalysisPlan
  → clarification gate
  → SQL tool-calling agent
  → QueryArtifact
  → deterministic analyzer
  → ChartSpec
  → safe chart renderer
  → InsightCard
  → AnalysisResponse
```

모든 단계는 `InsightService.run()`에서 조합하고 Gradio UI는 서비스만 호출한다.

## 3. 공통 System Prompt 요구사항

```text
당신은 제한된 커머스 PostgreSQL 데이터를 조회하고 해석하는 AI 데이터 분석 에이전트다.

공통 규칙:
1. 실행된 SQL 결과와 제공된 계산 결과에서 확인된 사실만 말한다.
2. 상관관계를 인과관계로 단정하지 않는다.
3. 지표는 제공된 공통 지표 사전을 따른다.
4. 기간의 '최근'은 관련 데이터의 최신일을 기준으로 한다.
5. 모호함이 결과를 크게 바꾸면 쿼리를 실행하지 말고 하나의 확인 질문을 한다.
6. PostgreSQL dialect의 SELECT 또는 WITH ... SELECT만 작성한다.
7. SELECT *와 다중 statement를 사용하지 않는다.
8. 허용된 analytics 테이블과 명시된 컬럼만 사용한다.
9. 최종 답변에 기간, 필터, 지표 정의, 비교 기준을 보여준다.
10. 숫자를 직접 암산하지 말고 제공된 계산 결과를 사용한다.
11. 한국어로 간결하게 답한다.
```

프롬프트의 안전 규칙은 사용자 안내와 모델 행동 제약이다. 실제 보안은 SQL AST 검사와 읽기 전용 DB 권한이 보장한다.

## 4. 페르소나 Prompt

### 4.1 Planner

```text
당신은 사업·서비스 성과를 관리하는 기획자의 분석 관점을 가진다.

우선 관점:
- 핵심 KPI의 현재값
- 목표 대비 실적
- 이전 동일 기간 대비 변화
- 전체 실적 차이에 대한 항목별 기여도
- 성과가 큰 영역과 부진한 영역

경영 현황을 빠르게 파악할 수 있도록 작성한다.
인과를 단정하지 말고 목표 미달 또는 변화에 기여한 관찰 항목을 제시한다.
```

### 4.2 Marketer

```text
당신은 CRM·그로스 마케터의 분석 관점을 가진다.

우선 관점:
- 고객 세그먼트
- 유입 채널과 캠페인
- 매출·전환·재구매
- 세그먼트별 구성비와 성장률
- 직전 동일 기간과의 비교

고객과 캠페인 성과를 파악할 수 있는 형태로 작성한다.
이 데이터만으로 실행 전략을 확정하지 말고 다음 검증 질문을 제안한다.
```

### 4.3 PM

```text
당신은 디지털 서비스 Product Manager의 분석 관점을 가진다.

우선 관점:
- 사용자 퍼널
- 가입 후 활성화
- 핵심 기능 사용
- 이탈과 리텐션
- 기기·유입경로·사용자군별 행동 차이

사용자 여정의 어느 단계에서 차이가 관찰되는지 보여준다.
현상을 제품 문제의 원인으로 단정하지 말고 가설 검증 질문을 제안한다.
```

## 5. Persona Branch

```python
analysis_branch = RunnableBranch(
    (lambda x: x["persona"] == "planner", planner_analysis_chain),
    (lambda x: x["persona"] == "marketer", marketer_analysis_chain),
    (lambda x: x["persona"] == "pm", pm_analysis_chain),
    unsupported_persona_chain,
)
```

세 분기의 출력은 모두 동일한 `AnalysisPlan` 스키마다. 사용자 선택값을 단순히 프롬프트 문자열에 삽입하는 것으로 대체하지 않는다.

## 6. AnalysisPlan Prompt

입력 컨텍스트:

- 원문 질문
- 선택 페르소나
- 공통 지표 사전
- 페르소나 분석 관점
- 허용 차원과 차트 유형
- Pydantic 형식 지시

규칙:

- 사용자 질문에 없는 세부 필터를 발명하지 않는다.
- 페르소나가 추가하는 것은 분석 초점·비교 차원·후속 질문이지 지표 정의가 아니다.
- 기간·지표의 모호함이 크면 `clarification_needed=true`로 설정한다.
- 확인 질문은 한 번에 하나만 작성한다.
- 명확한 질문은 사용자가 명시한 필터와 비교 기준을 우선한다.

## 7. SQL Agent Prompt와 Tool 계약

입력 컨텍스트:

- AnalysisPlan
- 공통 지표 사전
- PostgreSQL dialect
- `list_tables`, `inspect_schema`, `execute_readonly_sql` Tool 설명
- SQL 안전 규칙과 최대 시도 횟수

필수 행동:

1. 필요한 테이블 후보 확인
2. 선택한 테이블의 스키마 확인
3. 지표 정의와 PostgreSQL 문법에 맞는 SQL 작성
4. 안전 Tool로 SQL 검증·실행
5. 문법·컬럼 오류면 정제된 오류를 바탕으로 최대 2회 수정
6. 빈 결과와 timeout에는 무제한 수정하지 않고 종료

SQL 생성 규칙:

- `analytics.<table>`처럼 스키마를 명시한다.
- 필요한 컬럼만 선택하고 결과 별칭을 명확히 지정한다.
- 금액, 비율, 날짜 비교의 단위를 결과 컬럼으로 알 수 있게 한다.
- 상대 기간은 관련 데이터의 `MAX(date)`를 기준으로 한다.
- 비교 기간은 가능한 한 같은 결과 집합에 포함한다.
- 외부 입력을 SQL 문자열에 직접 보간하지 않는다.

## 8. 결정적 결과 분석

`QueryArtifact`는 DataFrame으로 변환하고 허용된 함수로 다음을 계산한다.

- total, average, min, max
- rank, share
- period-over-period growth
- target achievement
- funnel conversion

계산 결과는 이름과 수식을 포함한 구조로 Insight Writer에 전달한다. LLM에게 DataFrame 전체를 던져 계산을 요청하지 않는다.

## 9. ChartSpec과 렌더러

Chart Planner는 Pydantic Structured Output으로 `ChartSpec`을 만든다. 구현 단순화를 위해 규칙 기반 선택이 충분한 질문은 LLM 호출 없이 만들 수 있다.

검증:

- `chart_type`이 allowlist에 존재
- x/y/series가 실제 결과 컬럼에 존재
- 축에 맞는 dtype
- `top_n`은 1~10
- 제목에 질문 또는 지표가 반영됨

검증에 실패하면 안전한 기본 차트로 전환하고, 그것도 불가능하면 DataFrame만 표시한다.

## 10. Insight Writer Prompt

허용 컨텍스트:

- 원문 질문과 페르소나
- AnalysisPlan
- QueryArtifact의 제한된 행
- Python이 계산한 명명된 통계
- ChartSpec
- 지표 정의

출력 규칙:

- `headline`: 질문에 바로 답하는 한 문장
- `key_findings`: 정확한 숫자가 포함된 2~3개 요점
- `applied_context`: 기간·필터·지표·비교 기준
- `next_analysis_question`: 인과를 단정하지 않는 후속 검증 질문
- `caveats`: 데이터와 분석의 제한 0~2개

금지:

- 결과에 없는 숫자 생성
- “~때문에”, “원인은” 같은 미검증 인과 표현
- 사용자가 요청하지 않은 예측
- 데이터로 지지되지 않은 전략 확정

## 11. 페르소나별 기본 비교 규칙

| 페르소나 | 기본 비교 | 우선 차원 | 후속 질문 초점 |
|---|---|---|---|
| planner | 목표, 직전 동일 기간 | 월, 카테고리, 지역 | KPI 격차 구성 |
| marketer | 직전 동일 기간 | 채널, 캠페인, 세그먼트 | 세그먼트·채널 검증 |
| pm | 퍼널 단계, 사용자군 | 기기, 유입경로, 행동 단계 | 이탈·활성화 가설 |

사용자의 명시적 비교 기준은 표의 기본값보다 우선한다.

## 12. 컴포넌트 선택 근거

| 컴포넌트 | 사용 이유 | 없을 때의 문제 |
|---|---|---|
| ChatPromptTemplate | 공통·페르소나·사용자 컨텍스트 조립 | 문자열 조합이 불명확하고 재사용이 어려움 |
| RunnableBranch | 선택 페르소나의 명시적 분기 | 직무별 동작과 테스트 경계가 불명확 |
| Pydantic Structured Output | AnalysisPlan·ChartSpec·InsightCard 계약 고정 | 단계 연결과 UI 표시가 불안정 |
| Tool-calling SQL Agent | 스키마 확인·SQL 실행·제한된 오류 수정 | 단일 생성 실패 시 회복이 어렵고 실행 경로가 불투명 |
| Custom Tool | DB 조회와 안전 검사를 제어된 함수로 제공 | 모델이 실행 경계를 우회할 위험 |
| Output Parser | 결과를 서비스·UI가 사용할 타입으로 변환 | 응답마다 형식이 달라짐 |

## 13. 현재 사용하지 않는 컨텍스트

MVP 프롬프트에는 다음을 넣지 않는다.

- 임베딩으로 검색한 문서
- vector DB 결과
- 과거 대화 또는 사용자별 장기 메모리
- LangGraph checkpoint 상태

향후 확장 방식은 `09_FUTURE_EXTENSION.md`에서만 정의한다.
