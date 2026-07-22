# V0.2 ChatGPT Project Result

## 목표

사용자가 평범한 말로 목적을 설명하면 ChatGPT가 저장소의 패턴·workflow·active 정책을 이용해 다른 AI에서 바로 쓸 요청별 프롬프트를 새로 작성하도록 제품 방향을 복구했다.

## 최종 사용자 흐름

```text
사용자 요청
→ ChatGPT Project가 목적·제약·산출물 이해
→ baseline / pattern-only / active 선택
→ AI가 요청별 최종 프롬프트 작성
→ 한 번 자체 검증·수정
→ 실패 시 좁은 모드로 fallback
→ 다른 AI에서 사용할 프롬프트 반환
```

`scripts/prompt_runtime.py`는 AI 작성기가 아니라 로컬 deterministic template fallback으로 명시했다.

## Git 복구 범위

- baseline-first router, corpus pipeline, manifest와 스키마
- active 허용 목록 7개와 요청당 1개 제한
- 고정 prompt-mode 및 expert-collaboration 사례
- router·pipeline 테스트
- 인수인계·연구 큐·결과 inbox 운영 문서

대용량 `reports/`, UI 실험, 별도 실험 실행기는 기존 미추적 사용자 작업으로 보존하고 포함하지 않았다.

## ChatGPT Project 파일

- `chatgpt-project/PROMPT_COMPILER_INSTRUCTIONS.md`
- `chatgpt-project/README.md`
- `tests/test_chatgpt_prompt_compiler_contract.py`
- 탐색 경로를 갱신한 `README.md`, `USAGE.md`, `QUICKSTART.md`

## 검증

- 현재 전체 작업공간: 63/63 테스트 통과
- 현재 Git `HEAD`만 export한 깨끗한 복사본: 43/43 테스트 통과
- 깨끗한 복사본에서 `scripts/prompt_runtime.py` smoke: 종료 0, prompt와 routing JSON 생성
- ChatGPT compiler 계약: AI 작성 단계, full 비활성화, active 7개, 요청당 1개, copyable output, Git 비동기화 명시 통과

## 커밋

- `d85d0f4 Create v0.1 prompt runtime`
- `13e3185 Add baseline-first prompt router core`
- `6e61b59 Add ChatGPT prompt compiler project`
- 이 결과 문서는 `Record v0.2 prompt compiler result` 커밋에 포함

## GitHub 게시 상태

- 원격: `https://github.com/sarecury-lgtm/prompt-system-lab.git`
- 브랜치: `codex/close-prompt-improvement-loop`
- 로컬 commit 완료
- push·PR: `gh` CLI가 설치되어 있지 않아 GitHub 게시 workflow의 prerequisite에서 보류
- tag: PR merge와 깨끗한 원격 checkout 검증 전에는 생성하지 않음

## 다음 작업

`gh` CLI 설치·로그인 확인 후 현재 브랜치를 push하고 `main` 대상 draft PR을 만든다. PR merge 뒤 ChatGPT Project에 지침과 세 source 파일을 넣어 실제 요청 편차를 점검한다.
