# RoleLens 개발 문서

RoleLens는 기획자·마케터·PM이 직무를 선택하고 자연어로 데이터 질문을 입력하면, 공통 지표 정의와 직무별 분석 관점을 적용해 PostgreSQL을 조회하고 핵심 요약·시각화·후속 분석 질문을 제공하는 LangChain 기반 데이터 인사이트 에이전트다.

## 문서 목록

1. [기획안](./01_PROJECT_PROPOSAL.md)
2. [PRD](./02_PRD.md)
3. [기술 설계](./03_TECHNICAL_DESIGN.md)
4. [데이터·지표 명세](./04_DATA_AND_METRICS.md)
5. [프롬프트·체인 명세](./05_PROMPT_AND_CHAIN_SPEC.md)
6. [테스트 계획](./06_TEST_PLAN.md)
7. [구현 계획](./07_IMPLEMENTATION_PLAN.md)
8. [VS Code Codex 핸드오프](./08_CODEX_HANDOFF.md)
9. [향후 확장 설계](./09_FUTURE_EXTENSION.md)
10. [구현 결정·검증 기록](./10_IMPLEMENTATION_NOTES.md)

## 문서 우선순위

문서 간 충돌이 있을 경우 다음 순서로 판단한다.

1. `02_PRD.md`의 범위와 인수 조건
2. `04_DATA_AND_METRICS.md`의 지표 정의
3. `03_TECHNICAL_DESIGN.md`의 안전·아키텍처 제약
4. `05_PROMPT_AND_CHAIN_SPEC.md`의 프롬프트 규칙
5. 나머지 문서

## 최종 산출물

- 제출 형식: 실행 가능한 RoleLens 프로젝트 ZIP
- 권장 파일명: `{반}_{이름}_RoleLens.zip`
- 주요 실행물: Gradio Blocks 웹 UI
- DB: Docker Compose로 실행하는 PostgreSQL
- 데이터: 고정 seed로 재생성 가능한 Mock 커머스 데이터
- 프로토타입: 핵심 기능 검증용 Jupyter Notebook을 `notebooks/`에 포함
- 제외: 실제 `.env`, API 키, 비밀번호, 캐시, 가상환경, 생성 DB 볼륨

## MVP 개발 원칙

- PostgreSQL을 유일한 MVP DB로 사용하며 SQLite 대체 경로는 만들지 않는다.
- 범용 DB 에이전트가 아닌 제한된 커머스 데이터 도메인을 구현한다.
- 지표의 의미는 페르소나와 관계없이 고정하고, 페르소나는 분석 초점·비교 기준·설명 방식만 바꾼다.
- LLM은 질문 해석, SQL 생성, 서술을 담당하고 숫자 계산과 차트 렌더링은 결정적 Python 함수가 담당한다.
- 에이전트 DB 계정은 허용된 분석 스키마에 대한 읽기 권한만 가진다.
- UI는 서비스 계층의 공개 입력·출력 계약만 사용하고 LangChain과 DB 내부 구현에 직접 의존하지 않는다.
- RAG, LangGraph, vector DB는 현재 MVP에 구현하지 않는다. 향후 교체 가능한 경계만 유지한다.

## 예정 실행 흐름

```bash
cp .env.example .env
pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head
python scripts/seed_mock_data.py --seed 42
pytest
python -m rolelens.ui.gradio_app
```

실제 명령은 구현 중 선택한 패키지·마이그레이션 방식에 맞게 프로젝트 루트 `README.md`에서 최종 확정한다.
