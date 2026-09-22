# RoleLens 데이터·지표 명세

## 1. 데이터 설계 목표

- 기획자·마케터·PM의 대표 질문을 하나의 커머스 서비스 데이터로 검증한다.
- 조인·집계·기간 비교가 필요한 최소 스키마를 사용한다.
- Mock 데이터는 별도 seed 스크립트로 동일하게 재생성한다.
- 지표 정의와 분석 기준을 프롬프트, 정답 SQL, 테스트가 함께 사용한다.

## 2. 데이터 기준

- DB: PostgreSQL
- 스키마: `analytics`
- `RANDOM_SEED = 42`
- `DATA_AS_OF = 2026-09-15`
- 생성 기간: 2025-01-01 ~ 2026-09-15
- 금액 단위: KRW
- 타임존: Asia/Seoul
- 날짜 컬럼: `DATE`, 이벤트 시각이 필요하지 않은 MVP 기준

시스템 현재 시간이 아닌 데이터 기준일과 각 테이블의 최대 날짜를 상대 기간 해석에 사용한다.

## 3. ER 구조

```text
users 1 -------- N user_events
  |
  +------------- N orders N -------- 1 products
                           |
                           +-------- 0..1 campaigns

monthly_targets: 월·지표별 목표값
```

## 4. 테이블 명세

### 4.1 `analytics.users`

| 컬럼 | PostgreSQL 타입 | 제약·설명 |
|---|---|---|
| user_id | BIGINT | PK |
| signup_date | DATE | 가입일, NOT NULL |
| age | SMALLINT | 만 나이, 14~80 |
| region | VARCHAR(20) | 서울, 경기, 부산, 대구, 기타 |
| acquisition_channel | VARCHAR(20) | organic, search, social, display, referral |
| device | VARCHAR(20) | mobile, desktop, tablet |

### 4.2 `analytics.user_events`

| 컬럼 | PostgreSQL 타입 | 제약·설명 |
|---|---|---|
| event_id | BIGINT | PK |
| user_id | BIGINT | FK → users.user_id |
| event_date | DATE | 이벤트 발생일 |
| event_name | VARCHAR(30) | app_open, product_view, add_to_cart, checkout_start, feature_used |
| session_id | VARCHAR(64) | 세션 식별자 |

### 4.3 `analytics.products`

| 컬럼 | PostgreSQL 타입 | 제약·설명 |
|---|---|---|
| product_id | BIGINT | PK |
| product_name | VARCHAR(100) | 상품명 |
| category | VARCHAR(20) | beauty, fashion, food, living, digital |
| list_price | NUMERIC(14, 2) | 표준 판매가 |

### 4.4 `analytics.campaigns`

| 컬럼 | PostgreSQL 타입 | 제약·설명 |
|---|---|---|
| campaign_id | BIGINT | PK |
| campaign_name | VARCHAR(100) | 캠페인명 |
| channel | VARCHAR(20) | search, social, display, crm |
| start_date | DATE | 시작일 |
| end_date | DATE | 종료일 |
| spend | NUMERIC(14, 2) | 집행 비용 |

### 4.5 `analytics.orders`

MVP 복잡도를 줄이기 위해 주문 1건에 대표 상품 1개를 가정한다.

| 컬럼 | PostgreSQL 타입 | 제약·설명 |
|---|---|---|
| order_id | BIGINT | PK |
| order_date | DATE | 주문일 |
| user_id | BIGINT | FK → users.user_id |
| product_id | BIGINT | FK → products.product_id |
| campaign_id | BIGINT | NULL 허용, FK → campaigns.campaign_id |
| quantity | INTEGER | 1 이상 |
| sales_amount | NUMERIC(14, 2) | 할인 후 결제 금액 |
| status | VARCHAR(20) | completed, cancelled, refunded |

### 4.6 `analytics.monthly_targets`

| 컬럼 | PostgreSQL 타입 | 제약·설명 |
|---|---|---|
| target_month | DATE | 월의 첫날 |
| metric_name | VARCHAR(30) | revenue, new_customers |
| target_value | NUMERIC(16, 2) | 목표값 |
| persona_owner | VARCHAR(20) | planner |

PK는 `(target_month, metric_name)` 복합키다.

## 5. 공통 지표 사전

지표의 정의는 페르소나에 따라 바뀌지 않는다.

### Revenue

```sql
SUM(o.sales_amount) FILTER (WHERE o.status = 'completed')
```

- 한국어 동의어: 매출, 매출액, 결제 매출
- 취소·환불 주문 제외

### Orders

```sql
COUNT(DISTINCT o.order_id) FILTER (WHERE o.status = 'completed')
```

### Customers

```sql
COUNT(DISTINCT o.user_id) FILTER (WHERE o.status = 'completed')
```

### New Customer

사용자의 첫 완료 주문일이 분석 기간 내에 있으면 신규 고객이다.

```sql
MIN(o.order_date) FILTER (WHERE o.status = 'completed')
```

- `signup_date`만으로 신규 고객을 정의하지 않는다.
- PM의 “신규 가입자”는 `signup_date`를 사용하며 신규 고객과 구분한다.

### Average Order Value

```text
완료 주문 매출액 / 완료 주문 수
```

### Active User

분석 기간 내 `user_events`가 1건 이상 있는 고유 사용자다.

### 7-day Activation Rate

가입일로부터 7일 이내 `feature_used`를 1회 이상 발생시킨 가입자 비율이다.

```text
7일 이내 feature_used 가입자 수 / 전체 가입자 수
```

가입 후 7일의 관찰 기간이 데이터 기준일보다 뒤까지 필요한 가입자는 기본 분석에서 제외하거나 미성숙 cohort로 표시한다.

### Purchase Conversion Rate

```text
분석 기간 완료 구매 고객 수 / 분석 기간 활성 사용자 수
```

### Campaign ROAS

```text
해당 캠페인에 귀속된 완료 주문 매출 / 캠페인 spend
```

MVP의 단순 last-touch 귀속 가정을 주의사항에 표시한다.

### Target Achievement Rate

```text
실제 지표 / monthly_targets.target_value * 100
```

## 6. 기간 규칙

- “최근”의 기준일은 시스템 날짜가 아닌 관련 데이터의 최대 날짜다.
- “최근 3개월”은 최대 날짜를 포함한 달과 이전 2개 월의 시작일부터 최대 날짜까지다.
- “직전 3개월”은 현재 3개월 직전의 완전한 3개 월이다.
- “이번 분기”는 데이터 기준일이 속한 분기의 시작일부터 기준일까지다.
- 비교 기간 길이가 달라 절대값이 왜곡되면 일평균 또는 동일 경과일 비교를 사용하고 명시한다.
- PostgreSQL의 `date_trunc`, `interval`, `FILTER` 문법을 기준으로 정답 SQL을 작성한다.

## 7. 인구통계·범주 규칙

- 20대: `20 <= age AND age < 30`
- 30대: `30 <= age AND age < 40`
- 40대: `40 <= age AND age < 50`
- 기타 지역은 개별 범주로 정의하지 않은 잔여 지역이다.
- 영문 범주값은 출력에서 한국어 레이블로 변환할 수 있지만 SQL에서는 원본 값을 사용한다.

## 8. Mock 데이터 생성

`scripts/seed_mock_data.py`가 관리자 DB 연결을 사용해 데이터를 생성한다.

```bash
python scripts/seed_mock_data.py --seed 42
```

요구사항:

- 동일 seed와 기준일이면 행 수와 기준 집계가 동일하다.
- migration이 완료되지 않았으면 명확한 오류를 반환한다.
- FK 순서에 맞춰 적재한다.
- 재실행 시 중복되지 않도록 명시적 초기화 또는 idempotent upsert 전략을 사용한다.
- 적재 후 행 수, PK/FK 무결성, 날짜 범위, 범주값, 기준 SQL을 검증한다.
- 생성 패턴은 코드 주석과 문서에서 Mock임을 명시한다.

삽입할 대표 패턴:

- 2026년 7~9월 20대 beauty 매출은 직전 3개월 대비 증가
- 2026년 8~9월 social 채널 신규 고객은 감소
- mobile 가입자의 7일 활성화율은 desktop보다 낮음
- 2026년 3분기 매출은 목표에 소폭 미달
- cancelled/refunded 주문이 일정 비율 존재

## 9. 접근 제어와 노출 범위

- migration과 seed: `rolelens_owner`
- 에이전트 조회: `rolelens_agent_ro`
- 조회 허용: 위 6개 `analytics` 테이블
- 금지: `information_schema`, `pg_catalog`, Alembic 테이블, 다른 스키마
- 앱의 테이블 설명은 DB 원본 metadata에 업무 설명을 결합한 allowlist에서 제공한다.

## 10. 표준 질문과 필수 테이블

| 질문 | 필수 테이블 |
|---|---|
| 이번 분기 매출이 목표 대비 어떤가? | orders, monthly_targets |
| 최근 3개월 20대 고객의 카테고리별 매출은? | users, orders, products |
| 신규 가입자의 7일 이내 활성화율을 기기별로 보여줘. | users, user_events |
| 최근 신규 고객 수가 어떻게 변했어? | users, orders, 페르소나에 따라 campaigns/user_events/monthly_targets |

## 11. 기준 검증

seed 완료 후 테스트 fixture가 다음을 저장·검증한다.

- 테이블별 예상 행 수
- `MIN/MAX` 날짜
- 상태·범주별 건수
- 표준 질문 3개의 기준 집계
- 완료 주문 매출에 취소·환불이 포함되지 않는지 여부
- 7일 활성화율의 관찰 기간 처리

LLM이 생성한 SQL 결과는 기준 SQL의 핵심 숫자와 대조한다.
