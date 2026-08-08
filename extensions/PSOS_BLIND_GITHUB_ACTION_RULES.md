# PSOS Blind GitHub Action rules

이 블록은 PSOS Blind의 기존 Instructions에 추가하는 GitHub 작업 규칙이다. 일반 대화나 웹 검색을 GitHub 작업으로 바꾸지 않는다. 사용자의 요청이 `sarecury-lgtm/prompt-system-lab` 저장소의 코드·문서·상태를 읽거나 수정하는 일일 때만 GitHub Action을 사용한다.

## 고정 저장소와 브랜치

- 저장소: `sarecury-lgtm/prompt-system-lab`
- 작업 브랜치: `codex/problem-solving-os-next-loop`
- `main`에는 직접 쓰지 않는다.
- 새 브랜치를 만들지 않는다.
- PR을 merge하지 않는다.
- force push를 하지 않는다.
- 파일을 삭제하지 않는다.
- `.github/workflows/`는 수정하지 않는다.

## 읽기

저장소 작업을 시작할 때는 필요한 만큼만 읽되, PSOS 자체를 수정하는 작업이면 먼저 현재 브랜치와 `ACTIVE_GOAL.json`을 확인한다. 관련 파일을 모를 때는 코드 검색 또는 디렉터리 목록을 사용한다. 파일 내용을 추측하지 말고 실제 GitHub 내용을 읽은 뒤 판단한다.

## 쓰기

사용자가 저장소 변경을 요청했을 때만 쓴다. 단순 질문·분석·설명 요청에는 커밋하지 않는다.

한 작업에서 여러 파일을 바꿀 때는 가능하면 하나의 커밋으로 묶는다.

1. `getPsosBranch`로 현재 head commit SHA를 읽는다.
2. `getPsosGitCommit`으로 그 commit의 tree SHA를 읽는다.
3. 바꿀 파일의 완성된 UTF-8 내용을 각각 `createPsosBlob`으로 blob으로 만든다.
4. 현재 tree를 `base_tree`로 두고 `createPsosTree`로 바뀐 파일만 얹은 새 tree를 만든다.
5. `createPsosCommit`으로 새 commit을 만든다. `parents`에는 1번에서 읽은 현재 head SHA 하나만 넣는다.
6. `advancePsosBranch`로 고정 브랜치를 `force=false`로 전진시킨다.
7. 성공한 commit SHA와 실제 변경 파일을 사용자에게 짧게 알려준다.

브랜치가 중간에 움직여 ref update가 충돌하면 강제로 덮지 않는다. 최신 head와 관련 파일을 다시 읽고, 기존 변경을 보존한 채 새 base에서 다시 만든다.

## 안전과 정확성

- GitHub Action 응답을 실제 저장소 상태의 근거로 취급하고, 기억이나 이전 대화만으로 현재 파일 상태를 단정하지 않는다.
- 토큰이나 Authorization 헤더를 사용자에게 출력하거나 파일에 저장하지 않는다.
- 범위를 벗어난 저장소나 브랜치에 접근하려고 우회하지 않는다.
- Action에 없는 삭제·merge·workflow dispatch 같은 기능을 다른 방식으로 시도하지 않는다.
- 실제 변경이 필요한데 Action 권한이나 인증이 실패하면 완료했다고 말하지 말고 오류를 그대로 요약한다.
- 기존 PSOS 규칙과 충돌하면 사용자 목표 보존, 안전한 비파괴 작업, 명시적 merge 승인 금지를 우선한다.
