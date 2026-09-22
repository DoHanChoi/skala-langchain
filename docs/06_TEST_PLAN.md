# RoleLens 테스트 계획

## 1. 테스트 목표

- 직무 선택이 분석 계획과 설명 관점에 실제로 영향을 주는지 확인한다.
- SQL이 지표 사전, PostgreSQL 문법, 안전 규칙을 따르는지 확인한다.
- 요약의 모든 숫자가 실행 결과에서 검증되는지 확인한다.
- 질문 형태에 맞는 차트가 생성되는지 확인한다.
- PostgreSQL 초기화부터 Gradio 출력까지 새 환경에서 재현되는지 확인한다.
- 실패·모호함·위험 입력을 안전하게 처리하는지 확인한다.

## 2. 테스트 계층

### 2.1 단위 테스트

- 입력 Pydantic 검증
- 페르소나 분기 조건
- 지표 계산 함수
- 기간 계산 함수
- SQL AST 안전 검사
- ChartSpec 검증과 fallback
- UI 표시용 데이터 변환

단위 테스트는 가능한 한 실제 LLM과 DB 없이 실행한다.

### 2.2 PostgreSQL 통합 테스트

- migration 적용
- seed 재현성
- 읽기 전용 계정 권한
- table/schema Tool
- 안전 SQL 실행과 timeout
- 기준 SQL과 계산 결과

별도 테스트 DB 또는 일회성 Docker Compose 환경을 사용하며 개발 DB 데이터에 의존하지 않는다.

### 2.3 체인·서비스 테스트

- LLM을 stub/fake로 대체한 성공 흐름
- clarification 흐름
- SQL 수정 횟수 제한
- Structured Output 실패 처리
- InsightService의 상태별 응답 계약

### 2.4 수동 E2E

- Docker Compose → migration → seed → Gradio 실행
- 3개 표준 질문 실행
- 인사이트·차트·데이터·근거 영역 확인
- 오류 후 다음 질문을 계속 실행할 수 있는지 확인

## 3. 표준 시나리오

### TS-01 Planner

```text
페르소나: planner
질문: 이번 분기 매출이 목표 대비 어떤가?
```

기대:

- 이번 분기 실제 매출과 목표를 비교한다.
- 목표 달성률 또는 격차를 계산한다.
- 월별 실적과 목표 비교 차트를 생성한다.
- `completed` 주문만 매출에 사용한다.

### TS-02 Marketer

```text
페르소나: marketer
질문: 최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.
```

기대:

- users, orders, products를 조인한다.
- 20대를 `20 <= age AND age < 30`으로 적용한다.
- 현재 3개월과 직전 3개월 매출을 비교한다.
- grouped bar chart를 생성한다.
- 최대 매출 카테고리와 최대 증감 카테고리를 구분한다.

### TS-03 PM

```text
페르소나: pm
질문: 최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.
```

기대:

- users, user_events를 사용한다.
- 가입일로부터 7일 이내 `feature_used`를 활성화로 본다.
- 관찰 기간이 완성된 cohort 기준을 적용한다.
- 기기별 모수·활성화 사용자·활성화율을 제공한다.
- 기기별 bar chart를 생성한다.

## 4. 페르소나 분기 테스트

공통 질문:

```text
최근 신규 고객 수가 어떻게 변했어?
```

| 페르소나 | 기대 초점 |
|---|---|
| planner | 전체 신규 고객 KPI, 목표·이전 기간 격차, 매출 기여 |
| marketer | 유입 채널·캠페인별 신규 고객 변화 |
| pm | 가입·활성화·구매 전환 구간 |

검증 항목:

- `AnalysisPlan.metric`
- `dimensions`
- `comparison`
- `chart_hint`
- `next_analysis_question`

공통 지표 정의와 원문의 명시 조건은 페르소나에 따라 바뀌면 안 된다.

## 5. 모호함 테스트

```text
페르소나: marketer
질문: 요즘 잘 나가는 상품을 보여줘.
```

기대:

- “요즘”의 기간과 “잘 나가는”의 기준이 결과에 큰 영향을 준다고 판정한다.
- SQL Tool을 호출하지 않는다.
- 구체적인 확인 질문 하나를 반환한다.

예: “최근 30일의 매출액을 기준으로 상위 상품을 보여드릴까요?”

## 6. SQL 안전 테스트

| ID | 입력/상황 | 기대 |
|---|---|---|
| SEC-01 | `DROP TABLE analytics.orders` | 차단 |
| SEC-02 | `DELETE FROM analytics.orders` | 차단 |
| SEC-03 | `SELECT * FROM analytics.orders` | 차단 또는 명시 컬럼으로 재생성 |
| SEC-04 | `SELECT 1; DROP TABLE ...` | 다중 statement 차단 |
| SEC-05 | allowlist 밖의 테이블 | 차단 |
| SEC-06 | `pg_catalog`, `information_schema` | 차단 |
| SEC-07 | INSERT CTE를 포함한 WITH | 차단 |
| SEC-08 | 100행 초과 결과 | 제한 적용 |
| SEC-09 | 장시간 쿼리 | statement timeout |
| SEC-10 | read-only 계정으로 DDL/DML | PostgreSQL 권한에서 거부 |

검사기는 문자열 포함 검사에만 의존하지 않고 PostgreSQL AST를 검사한다.

## 7. 데이터·지표 테스트

- 동일 seed를 두 번 생성했을 때 행 수와 기준 집계 일치
- FK 위반 0건
- 날짜가 생성 범위 안에 있음
- completed 매출에서 cancelled/refunded 제외
- 신규 고객이 첫 완료 주문일 기준으로 계산됨
- 신규 가입자와 신규 고객의 정의가 섞이지 않음
- 7일 활성화율에서 미성숙 cohort가 제외 또는 표시됨
- 목표 달성률 분모가 0이면 안전하게 처리

## 8. 요약 충실도 테스트

각 `key_findings`의 숫자를 QueryArtifact 또는 계산 통계와 대조한다.

- 완전 일치 또는 표시 자릿수에 맞는 반올림: PASS
- 근거 없는 숫자: FAIL
- 기간·분모·필터가 다른 숫자: FAIL
- 상관관계를 원인으로 표현: FAIL
- Mock 데이터 밖의 시장 사실을 주장: FAIL

초기 MVP에서는 자동 숫자 추출 검사와 수동 체크리스트를 함께 사용한다.

## 9. 시각화 QA

- 제목이 질문과 지표에 일치한다.
- x/y축 레이블과 단위가 표시된다.
- 금액과 비율의 표기 형식이 일관된다.
- 범주가 10개를 초과하지 않는다.
- 긴 레이블이 잘리지 않는다.
- 한글 폰트가 깨지지 않거나 영문 레이블 fallback이 동작한다.
- 색상 의미가 비교 series마다 일관된다.
- ChartSpec 실패 시 DataFrame fallback이 동작한다.

## 10. Gradio UI QA

- 기본 페르소나와 예시 질문이 표시된다.
- 빈 질문은 모델 호출 전에 차단된다.
- 분석 중 중복 제출을 방지하거나 상태를 표시한다.
- 성공 응답이 네 영역에 올바르게 매핑된다.
- clarification 응답은 이전 결과와 혼동되지 않는다.
- 오류 메시지에 비밀번호·접속 문자열·스택 트레이스가 노출되지 않는다.
- 한 요청 실패 후 다음 요청이 정상 실행된다.

## 11. 재현성·패키징 테스트

깨끗한 환경에서 다음을 확인한다.

1. ZIP 압축 해제
2. `.env.example`을 `.env`로 복사하고 개인 API 키 입력
3. Docker Compose로 PostgreSQL 시작
4. migration 실행
5. seed 실행
6. `pytest` 실행
7. Gradio 앱 실행
8. 표준 질문 실행

제출 ZIP 검사:

- 실제 `.env`, API 키, 실제 비밀번호 없음
- `.venv`, 캐시, DB volume, 로그 없음
- README, 의존성 잠금 또는 명세, migration, seed, 테스트 포함
- RAG·LangGraph·vector DB 패키지가 불필요하게 포함되지 않음

## 12. 통과 기준

- 모든 단위 테스트 통과
- PostgreSQL 통합 테스트 통과
- SEC-01~10 차단 또는 제한 성공
- TS-01~03 핵심 숫자가 기준 SQL과 일치
- 세 페르소나의 공통 질문 AnalysisPlan이 의도대로 다름
- Gradio 앱에서 성공·clarification·error 세 상태가 정상 표시
- 깨끗한 환경의 README 실행 순서 완료
