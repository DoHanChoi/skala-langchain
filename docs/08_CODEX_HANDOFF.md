# VS Code Codex 핸드오프

## 1. 작업 목표

프로젝트 루트의 `docs` 문서를 기준으로 RoleLens MVP를 구현한다. 최종 산출물은 PostgreSQL, Mock 데이터 seed, LangChain 분석 파이프라인, Gradio Blocks UI, 테스트, 실행 문서를 포함한 프로젝트 ZIP이다.

Jupyter Notebook은 `notebooks/01_prototype.ipynb`에서 핵심 기술을 먼저 검증하는 용도이며 최종 애플리케이션 진입점이 아니다.

## 2. 필수 읽기 순서

1. `README.md`
2. `02_PRD.md`
3. `04_DATA_AND_METRICS.md`
4. `03_TECHNICAL_DESIGN.md`
5. `05_PROMPT_AND_CHAIN_SPEC.md`
6. `06_TEST_PLAN.md`
7. `07_IMPLEMENTATION_PLAN.md`
8. `01_PROJECT_PROPOSAL.md`
9. `09_FUTURE_EXTENSION.md`

문서가 충돌하면 PRD의 범위와 인수 조건을 우선한다.

## 3. 구현 전 점검

- 작업 폴더의 기존 LangChain 예제를 확인해 실제 설치 버전과 모델 초기화 방식을 파악한다.
- 사용 가능한 LLM provider, 모델, API 환경변수 이름을 확인한다.
- Docker와 Docker Compose 사용 가능 여부를 확인한다.
- PostgreSQL 포트 충돌과 필요한 환경변수를 확인한다.
- PRD Must 요구사항을 구현 체크리스트로 변환한다.
- 제안한 프로젝트 구조, 명령, 의존성이 현재 환경에서 실행 가능한지 확인한다.
- 문서와 충돌하거나 사용자의 결정이 필요한 사항은 코드를 작성하기 전에 보고한다.

API 키, 실제 DB 비밀번호, 전체 접속 문자열을 출력하거나 파일에 하드코딩하지 않는다.

## 4. 핵심 구현 제약

- PostgreSQL을 유일한 MVP DB로 사용하고 SQLite fallback을 만들지 않는다.
- 세 페르소나는 `planner`, `marketer`, `pm`으로 고정한다.
- 페르소나는 `RunnableBranch`로 명시적으로 분기한다.
- 분기 결과는 동일한 `AnalysisPlan` 스키마를 사용한다.
- 공통 지표 정의는 페르소나에 따라 바꾸지 않는다.
- SQL은 PostgreSQL dialect로 생성한다.
- SQL 안전성은 프롬프트만이 아니라 AST 검사, allowlist, read-only 계정으로 보장한다.
- LLM이 숫자를 임의 계산하거나 자유로운 Python 코드를 실행하게 하지 않는다.
- 차트는 구조화된 ChartSpec을 검증한 뒤 안전한 렌더러가 생성한다.
- 모든 숫자 주장은 SQL 결과 또는 Python 통계에서 검증 가능해야 한다.
- UI는 InsightService만 호출하며 DB와 agent 모듈을 직접 조립하지 않는다.
- RAG, LangGraph, vector DB, pgvector, FastAPI, React를 현재 구현에 추가하지 않는다.
- 향후 확장을 이유로 사용하지 않는 빈 모듈과 의존성을 만들지 않는다.

## 5. 작업 순서

`07_IMPLEMENTATION_PLAN.md`의 Phase 0~8을 따른다.

1. 환경과 패키지 버전 확인
2. PostgreSQL, migration, Mock seed와 정답 SQL
3. 프로토타입 노트북
4. 도메인·DB 모듈과 안전 계층
5. LangChain 분석 파이프라인
6. 후처리·차트·Insight Card
7. InsightService
8. Gradio Blocks UI
9. 테스트, README, ZIP 검증

각 Phase 종료 시 해당 완료 조건과 테스트를 확인한 뒤 다음으로 진행한다. 구현 중 실제 API가 문서와 다르면 사용자 경험과 안전 조건을 보존하면서 최신 설치 버전에 맞추고 변경 이유를 문서에 남긴다.

## 6. 필수 시나리오

1. Planner: `이번 분기 매출이 목표 대비 어떤가?`
2. Marketer: `최근 3개월간 20대 고객의 카테고리별 매출을 직전 3개월과 비교해줘.`
3. PM: `최근 3개월 신규 가입자의 7일 이내 핵심 기능 활성화율을 기기별로 보여줘.`
4. 공통 비교: `최근 신규 고객 수가 어떻게 변했어?`
5. 모호함: `요즘 잘 나가는 상품을 보여줘.`

## 7. 변경 관리

- 문서에 없는 페르소나, 테이블, 외부 API를 임의로 추가하지 않는다.
- 데이터 스키마 또는 지표 정의가 바뀌면 `04_DATA_AND_METRICS.md`와 기준 SQL을 함께 수정한다.
- 공개 입력·출력 계약이 바뀌면 PRD, 서비스 테스트, Gradio 매핑을 함께 수정한다.
- 패키지 API 때문에 기술 설계를 바꿔도 PRD의 인수 조건과 SQL 안전 계층을 약화하지 않는다.
- 사용하지 않는 복잡도보다 Must 요구사항, 재현성, 테스트를 우선한다.
- 기존 사용자 파일과 관계없는 변경을 되돌리지 않는다.

## 8. 검증 명령의 목표 형태

구현 후 루트 README에 실제 명령을 확정한다.

```bash
cp .env.example .env
pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head
python scripts/seed_mock_data.py --seed 42
pytest
python -m rolelens.ui.gradio_app
```

명령이 달라지면 README와 본 문서의 예시를 일치시킨다.

## 9. 완료 보고 형식

- 생성·수정한 주요 파일
- 선택한 모델·주요 패키지와 버전
- PostgreSQL 초기화·migration·seed 결과
- 구현한 LangChain 컴포넌트
- 실행한 단위·통합·E2E 테스트와 결과
- 표준 시나리오 결과
- 문서 대비 변경 사항과 남은 한계
- ZIP 생성 경로와 비밀정보 검사 결과

## 10. VS Code Codex 시작 프롬프트

```text
docs/08_CODEX_HANDOFF.md를 먼저 읽고, 명시된 순서로
RoleLens 개발 문서를 모두 확인해줘.

그 다음 07_IMPLEMENTATION_PLAN.md의 Phase 0부터 순서대로 구현해줘.
최종 산출물은 PostgreSQL, Mock seed, LangChain 분석 파이프라인,
Gradio Blocks UI, 테스트, 실행 README를 포함한 프로젝트야.

Jupyter Notebook은 핵심 기술 검증용으로 먼저 만들고, 검증된 로직은
src/rolelens 모듈과 InsightService로 추출해줘.

코드를 작성하기 전에 현재 환경, 수업 예제의 LangChain 버전,
사용 가능한 모델, Docker 실행 가능 여부, 제안 프로젝트 구조,
문서와 충돌하는 사항을 먼저 점검해서 보고해줘.

RAG, LangGraph, vector DB는 현재 구현하지 마.
```
