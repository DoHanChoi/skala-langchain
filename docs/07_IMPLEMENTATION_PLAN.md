# RoleLens 구현 계획

## 1. 구현 전략

핵심 기술을 작은 노트북에서 먼저 검증한 후 애플리케이션 모듈로 추출한다. 최종 제출물은 노트북이 아니라 Gradio UI와 PostgreSQL 환경을 포함한 프로젝트 ZIP이다.

원칙:

- 수동 정답 SQL을 먼저 만들고 LLM SQL과 비교한다.
- 노트북 검증 코드가 최종 서비스의 별도 구현으로 남지 않게 공통 모듈로 이동한다.
- UI보다 도메인·DB·서비스 계약을 먼저 안정화한다.
- Must 요구사항을 완료하기 전 RAG, LangGraph, vector DB를 도입하지 않는다.

## 2. 단계별 계획

### Phase 0 환경·결정 확인

- [x] Python과 수업 LangChain 예제 버전 확인
- [x] 사용할 LLM provider, 모델, 환경변수 이름 확인
- [x] Docker와 Docker Compose 실행 확인
- [x] 프로젝트 `pyproject.toml`과 `src` layout 초기화
- [x] `.env.example`, `.gitignore` 작성

완료 조건:

- 모델에 간단한 한국어 요청을 보내고 응답을 받는다.
- Python에서 임시 PostgreSQL 연결을 확인한다.

### Phase 1 PostgreSQL·Mock 데이터

- [x] `docker-compose.yml` 작성
- [x] owner와 read-only 역할 및 `analytics` 스키마 설계
- [x] SQLAlchemy 모델·Alembic migration 구현
- [x] 고정 seed 데이터 생성기 구현
- [x] `scripts/seed_mock_data.py` 구현
- [x] PK/FK·날짜·범주·행 수 검증
- [x] 표준 질문 3개의 정답 SQL 작성
- [x] read-only 계정의 DDL/DML 거부 확인

완료 조건:

- DB를 새로 만들어도 같은 행 수와 기준 집계가 생성된다.
- TS-01~03의 정답 SQL 결과를 얻는다.

### Phase 2 프로토타입 노트북

- [x] `notebooks/01_prototype.ipynb` 생성
- [x] 환경변수 기반 모델·DB 연결
- [x] 공통·페르소나 Prompt 검증
- [x] `RunnableBranch`와 `AnalysisPlan` 검증
- [x] 최소 SQL Tool로 표준 질문 1개 실행
- [x] 결과 DataFrame, 기본 차트, 요약 확인
- [x] 노트북에서 발견한 설계 차이를 문서에 반영

완료 조건:

- 한 질문이 `입력 → AnalysisPlan → SQL → 결과 → 차트 → 요약`으로 끝까지 실행된다.
- 노트북에 API 키와 비밀번호가 포함되지 않는다.

### Phase 3 도메인·DB 모듈 추출

- [x] Pydantic 도메인 모델 구현
- [x] 공통 지표·기간 함수 구현
- [x] 설정 모델 구현
- [x] DB engine과 repository 구현
- [x] table/schema Tool 구현
- [x] PostgreSQL AST 안전 검사기 구현
- [x] read-only 실행 Tool과 QueryArtifact 구현
- [x] 단위·통합 테스트 작성

완료 조건:

- 노트북 없이 DB Tool과 지표 함수를 pytest로 검증한다.
- SEC-01~10이 코드 검사 또는 DB 권한에서 차단된다.

### Phase 4 LangChain 분석 파이프라인

- [x] 공통 System Prompt 구현
- [x] 세 페르소나 Prompt 구현
- [x] `RunnableBranch` 구현
- [x] Structured Output 기반 AnalysisPlan 구현
- [x] 모호함 gate 구현
- [x] SQL Agent와 Tool 연결
- [x] 최대 2회 오류 수정
- [x] 단계별 구조화 trace 구현

완료 조건:

- 세 페르소나가 동일한 출력 타입을 반환한다.
- 공통 질문에서 분석 관점이 의미 있게 달라진다.
- 명확한 질문은 SQL을 실행하고 모호한 질문은 Tool을 호출하지 않는다.

### Phase 5 후처리·시각화·Insight Card

- [x] QueryArtifact → DataFrame 변환
- [x] 순위·구성비·증감률·달성률·전환율 함수 구현
- [x] ChartSpec 생성과 검증 구현
- [x] matplotlib/seaborn 렌더러 구현
- [x] 차트 실패 시 DataFrame fallback
- [x] 근거 중심 Insight Writer 구현
- [x] 숫자 주장 대조 로직 또는 테스트 구현

완료 조건:

- TS-01~03에서 적절한 차트가 생성된다.
- 숫자 계산은 LLM이 아닌 Python에서 수행된다.
- Insight Card의 숫자를 QueryArtifact 또는 계산 통계에서 찾을 수 있다.

### Phase 6 InsightService 통합

- [x] `InsightService.run(AnalysisRequest)` 구현
- [x] success·clarification·error 응답 계약 구현
- [x] LLM·DB·renderer 의존성 주입
- [x] 표준 시나리오 서비스 테스트
- [x] timeout·빈 결과·parser 오류 처리

완료 조건:

- UI나 노트북 없이 서비스 호출만으로 전체 흐름을 검증한다.
- 한 요청의 실패가 다음 요청에 영향을 주지 않는다.

### Phase 7 Gradio Blocks UI

- [x] 페르소나 선택과 예시 질문
- [x] 질문 입력과 분석 버튼
- [x] 상태·오류·확인 질문 표시
- [x] 인사이트 영역
- [x] 시각화 영역
- [x] 데이터 테이블 영역
- [x] SQL·필터·테이블·기준일 근거 영역
- [x] UI가 InsightService만 호출하도록 연결
- [x] 수동 UI QA

완료 조건:

- TS-01~03을 UI에서 실행할 수 있다.
- success·clarification·error 상태가 구분되어 표시된다.
- SQL 오류가 나도 앱 프로세스가 유지된다.

### Phase 8 재현성·제출 패키징

- [x] 프로젝트 루트 README 작성
- [x] 설치·DB 시작·migration·seed·test·app 명령 검증
- [x] 깨끗한 환경에서 전체 실행
- [x] 라이선스가 필요한 외부 데이터가 없는지 확인
- [x] 실제 `.env`, API 키, 비밀번호, DB volume, 캐시 제거
- [x] 제출 ZIP 생성
- [x] ZIP을 별도 폴더에 풀어 최종 스모크 테스트

완료 조건:

- PRD Definition of Done과 `06_TEST_PLAN.md` 통과
- ZIP 하나만으로 문서와 실행에 필요한 프로젝트 파일이 전달된다.

## 3. 의존 관계

```text
Phase 0
  └─> Phase 1 PostgreSQL·데이터
        └─> Phase 2 프로토타입
              └─> Phase 3 모듈 추출
                    └─> Phase 4 LangChain 파이프라인
                          └─> Phase 5 결과 생성
                                └─> Phase 6 서비스 통합
                                      └─> Phase 7 Gradio UI
                                            └─> Phase 8 패키징
```

Phase 2에서 검증된 아이디어를 Phase 3 이후 모듈로 옮기며, 노트북이 독립적인 운영 구현을 가지지 않게 한다.

## 4. 구현 우선순위와 축소 순서

시간이 부족하면 다음 순서로 범위를 축소한다.

1. SQL 오류 자동 수정을 2회에서 1회로 축소
2. `scatter`, `stacked_bar` 차트 제외
3. trace UI를 간단한 표로 축소
4. 공통 질문 페르소나 비교를 자동 화면이 아닌 테스트로 유지
5. 후속 분석 질문을 단순한 규칙 기반으로 대체

삭제하지 않는 항목:

- 세 페르소나와 RunnableBranch
- AnalysisPlan Structured Output
- PostgreSQL과 read-only 계정
- SQL AST 검사와 allowlist
- 표준 시나리오 3개
- SQL·테이블·차트·요약·근거
- Gradio UI와 InsightService 분리
- seed 재현성과 실행 README

## 5. 품질 게이트

각 Phase 완료 전에 다음을 확인한다.

- 코드가 문서의 데이터·입출력 계약과 일치하는가?
- 새 비밀값이나 하드코딩된 접속 정보가 없는가?
- 실패 시 사용자가 해결 가능한 메시지를 받는가?
- 결정적 로직과 LLM 판단이 분리되어 있는가?
- 테스트가 실제 결함을 잡을 수 있는가?
- 현재 범위 밖의 기술이 우발적으로 들어오지 않았는가?

## 6. 최종 체크리스트

- [x] PostgreSQL 초기화와 seed 재생성 성공
- [x] 프로토타입 노트북의 핵심 흐름 성공
- [x] 세 페르소나 표준 시나리오 성공
- [x] 공통 질문의 페르소나별 차이 확인
- [x] 위험 SQL과 read-only 권한 테스트 성공
- [x] 숫자 요약의 근거 대조 완료
- [x] Gradio의 네 결과 영역 표시
- [x] 모든 자동 테스트 통과
- [x] README를 따른 깨끗한 환경 실행 성공
- [x] ZIP 비밀정보·캐시·DB volume 검사 완료
