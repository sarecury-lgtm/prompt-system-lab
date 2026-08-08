# PSOS Blind ↔ GitHub Action setup

목표는 PSOS Blind가 Codex 대신 `sarecury-lgtm/prompt-system-lab`의 실험 브랜치를 읽고, 사용자가 저장소 변경을 요청한 경우에만 안전하게 커밋할 수 있게 만드는 것이다.

이 연결은 GitHub App이 아니라 **Custom GPT Action → GitHub REST API**를 사용한다. Action schema는 `extensions/psos-blind-github-action.openapi.yaml`, 실행 규칙은 `extensions/PSOS_BLIND_GITHUB_ACTION_RULES.md`에 있다.

## 1. GitHub fine-grained PAT 만들기

GitHub에서 Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token으로 이동한다.

권장 설정:

- Token name: `psos-blind-action`
- Resource owner: `sarecury-lgtm`
- Repository access: `Only select repositories`
- Selected repository: `prompt-system-lab`
- Repository permissions → Contents: `Read and write`
- Workflows: 권한을 주지 않는다.
- 가능한 짧은 만료일을 사용하고 필요하면 갱신한다.

토큰은 생성 직후 한 번만 보이므로 안전한 곳에 복사한다. 저장소나 GPT Instructions/Knowledge 파일에 토큰을 적지 않는다.

## 2. PSOS Blind에 Action 추가

ChatGPT에서 PSOS Blind 편집 화면을 열고 Configure → Actions → Create new action으로 이동한다.

Authentication:

- Authentication type: `API Key`
- Auth type: `Bearer`
- API key: 방금 만든 fine-grained PAT

Schema:

- `extensions/psos-blind-github-action.openapi.yaml`의 전체 내용을 붙여 넣는다.
- 스키마가 저장되면 액션 목록에 `getPsosBranch`, `getPsosContent`, `searchPsosCode`, `createPsosBlob`, `createPsosTree`, `createPsosCommit`, `advancePsosBranch` 등이 보여야 한다.

## 3. Instructions에 GitHub 규칙 추가

기존 PSOS Blind Instructions를 지우지 말고 `extensions/PSOS_BLIND_GITHUB_ACTION_RULES.md` 내용을 뒤쪽에 추가한다.

핵심은 다음과 같다.

- 일반 질문에는 GitHub를 쓰지 않는다.
- PSOS 저장소 작업을 시작할 때 현재 브랜치와 `ACTIVE_GOAL.json`을 실제로 읽는다.
- 쓰기는 `codex/problem-solving-os-next-loop` 브랜치에만 한다.
- main, merge, delete, force push, workflow 수정 기능은 사용하지 않는다.
- 여러 파일 수정은 blob → tree → commit → non-force ref update 순서로 하나의 커밋에 묶는다.

## 4. 먼저 읽기 테스트

Preview에서 다음처럼 요청한다.

`GitHub Action으로 현재 PSOS 작업 브랜치의 ACTIVE_GOAL.json을 읽고 current_task.id만 말해줘.`

정상이라면 Action 승인 UI가 뜬 뒤 실제 브랜치의 `ACTIVE_GOAL.json`을 읽어 답해야 한다. 저장소 내용을 기억으로 답하거나 웹 검색 결과로 대체하면 연결 검증 실패다.

## 5. 실제 쓰기

읽기 테스트가 된 뒤부터는 평소처럼 말하면 된다.

예:

`현재 PSOS 브랜치를 읽고, 방금 만든 Blind handoff의 UI 문구를 더 이해하기 쉽게 고쳐줘. merge는 하지 마.`

Blind는 관련 파일을 읽고 수정안을 만든 뒤 같은 고정 브랜치에 커밋한다. 완료 답변에는 commit SHA와 바뀐 파일만 짧게 남기는 것을 기본으로 한다.

## 이 Action이 일부러 못 하는 것

스키마에 다음 기능을 노출하지 않았다.

- 파일 삭제
- 브랜치 생성
- main 직접 수정
- PR merge
- release/issue 생성
- workflow dispatch
- force push

따라서 PSOS Blind를 Codex 대체 실행기로 쓰더라도 저장소 전체 권한을 그대로 넘기지 않는다.

## ZIP의 역할

GitHub 연결 뒤에는 코드·문서·프로젝트 상태를 ZIP으로 반복 전달하지 않는다. Git에 없는 현재 대화의 결정, 로컬 이미지, 아직 커밋하지 않은 외부 자료 등만 필요할 때 handoff ZIP으로 보충한다.

## 공식 문서

- OpenAI GPT Actions: https://help.openai.com/en/articles/9442513
- GitHub fine-grained PAT 관리: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- GitHub REST contents/Git database permissions: https://docs.github.com/en/rest
