# PSOS Goal Guard

## 목적

이 장치는 PSOS의 이미 정해진 상위 목적이 최근 실험이나 대표 사례에 의해 바뀌는 것을 막는다.

PSOS의 제품 목표는 쇼핑, 후보 교정, 프롬프트 생성, 주식 분석 중 하나가 아니다. 평범한 사용자 요청을 받아 목표와 제약을 보존하고, 직접 답변·조사·재사용·프롬프트·코드·파일·도구·검증 중 가장 작은 충분 조합을 선택해 빠르고 좋은 실제 결과를 만드는 범용 문제해결 시스템이다.

## 파일

- `AGENTS.md`: Codex와 다른 저장소 작업 에이전트가 자동으로 읽는 최상위 작업 규칙
- `ACTIVE_GOAL.json`: 현재 상위 목적, 금지된 목표 축소, 현재 승인 작업과 완료 조건
- `governance/PSOS_CHANGE_SCOPE.json`: 현재 브랜치 파일을 `CORE`, `ADAPTER`, `DOMAIN`, `TEST`로 분류
- `governance/PSOS_CROSS_DOMAIN_REGRESSION.json`: 단일 사례를 범용 개선으로 오인하지 않게 하는 서로 다른 문제군
- `scripts/problem_solving_goal_guard.py`: 위 계약과 실제 변경 파일을 검사하는 실행기

## 분류

- `CORE`: 관련 없는 여러 요청 종류에서 공통으로 필요한 기능
- `ADAPTER`: Codex, 수동 ChatGPT, 브라우저, 검색, 파일 패치처럼 코어를 실행하거나 연결하는 방식
- `DOMAIN`: 쇼핑처럼 특정 분야나 작업군에서만 사용하는 선택 도구
- `TEST`: 실험, 평가, 회귀 사례, 문서와 CI

`DOMAIN`과 `TEST`는 기본 실행 경로가 될 수 없다. `CORE`라는 이름을 쓰려면 같은 도메인 중복 사례가 아니라 최소 네 개의 서로 다른 문제군에서 같은 도메인 중립 인터페이스로 증거가 있어야 한다. 기본 승격은 그 뒤에도 별도 사용자 승인이 필요하다.

## 약한 진행 명령

`ㄱㄱ`, `진행`, `계속`, `go ahead`, `continue`는 `ACTIVE_GOAL.json`의 `current_task`만 이어서 실행한다. 다음은 별도 승인 없이는 하지 않는다.

- 상위 목적 변경
- 새 도메인 구현
- DOMAIN 또는 TEST를 CORE로 승격
- 실험 경로를 기본 UI나 런처에 연결
- PR 병합

## 실행

브랜치 전체를 `main`과 비교한다.

```powershell
python -B scripts/problem_solving_goal_guard.py --base origin/main
```

명시한 파일만 검사할 수도 있다.

```powershell
python -B scripts/problem_solving_goal_guard.py `
  --changed-file scripts/problem_solving_os.py `
  --changed-file tests/test_problem_solving_goal_guard.py
```

검사기는 다음 상황에서 실패한다.

- 분류되지 않은 변경 파일
- 하나의 파일이 둘 이상의 구성요소에 중복 분류됨
- 쇼핑 구현을 CORE로 선언함
- DOMAIN 또는 TEST를 기본 실행으로 켬
- 범용 회귀 도메인이 네 개 미만임
- 약한 진행 명령을 범위 확장 승인으로 바꿈
- 기존 마스터 문서나 현재 목적 파일을 필수 읽기에서 제거함

## 현재 브랜치 재분류

- 적응형 쇼핑 수집기: `DOMAIN`
- 후보 작업대와 교정 루프: `TEST`
- 수동 ChatGPT와 Codex Job Packet: `ADAPTER`
- Goal/Context, 범용 라우팅, 완료 검증과 제한된 재계획: 교차 도메인 검증 전까지 `CORE candidate`

이 분류는 기존 실험을 삭제하지 않는다. 실험이 본체를 대신하거나 성공 사례 하나로 기본 경로가 되는 것을 막는다.
