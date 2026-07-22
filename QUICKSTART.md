# Prompt Compiler 빠른 시작

## 준비 사항

- ChatGPT에 로그인되어 있어야 합니다.
- 별도의 OpenAI API 키나 API 요금은 필요하지 않습니다.
- 처음 GitHub 자료를 읽을 때 `raw.githubusercontent.com` 연결 승인이 나타납니다.

## 가장 간단한 실행 방법

1. [Prompt Compiler](https://chatgpt.com/g/g-6a606afd43308191baea14153489e228-prompt-compiler)를 엽니다.
2. 평소 말하듯 원하는 작업을 입력합니다.
3. GitHub 연결 창이 나타나면 `이번만 허용`을 누릅니다.
4. `바로 쓸 프롬프트`를 복사해 원하는 다른 AI에서 사용합니다.

## 요청 문자열 예시

```text
노트북 세 모델을 가격, 무게, 배터리, 수리 가능성으로 비교하고 상황별 추천을 내리게 하는 프롬프트를 만들어줘. 확인 안 된 값은 추정하지 마.
```

## 파일을 같이 넣는 예시

채팅 입력창의 파일 추가 버튼으로 파일을 첨부한 뒤 다음처럼 입력합니다.

```text
첨부한 회의록에서 결정 사항, 담당자, 기한을 JSON으로 추출하게 하는 프롬프트를 만들어줘. 없는 값은 null로 표시하게 해줘.
```

## 최종 결과 위치

결과는 같은 ChatGPT 대화의 `바로 쓸 프롬프트`에 표시됩니다. 아래 `선택 기록`에는 모드, 선택 이유, 사용 패턴, active source, fallback 여부가 표시됩니다.

## 오류가 발생했을 때 확인할 것

1. GitHub 연결 창에서 `이번만 허용`을 눌렀는지 확인합니다.
2. 승인 직후 ChatGPT가 일시 오류를 보이면 새 채팅에서 같은 요청을 한 번 다시 보냅니다.
3. 연결을 거절하면 현재 ChatGPT 동작상 그 응답이 중단되므로 새 채팅을 열어 다시 요청합니다.
4. GitHub 장애가 의심되면 잠시 뒤 다시 시도합니다.

## 작동 원리

Prompt Compiler의 AI가 사용자 요청을 이해하고, GitHub에 게시된 catalog에서 필요한 패턴을 고른 뒤 해당 상세 card를 읽어 요청별 프롬프트를 새로 작성합니다. GitHub는 자료 저장소이고, 실제 이해와 작성은 ChatGPT 구독 안의 AI가 담당합니다.

정책은 baseline-first, pattern-only 우선, active 허용 목록 7개, 요청당 active 최대 1개, 고유 기여가 없으면 fallback, full corpus 자동 검색 비활성화를 유지합니다. `global-response-v3.1`은 별도 작업 패턴이 아니라 최종 목적 보존 검사로 사용합니다.

## 개발자용 검증

```powershell
python scripts/build_chatgpt_action_runtime.py --check
python -m unittest discover -s tests -v
```

로컬의 기존 명령형 runtime은 [RESULT_INBOX/V0_1_RUNTIME_RESULT.md](RESULT_INBOX/V0_1_RUNTIME_RESULT.md)에 보존되어 있습니다. 현재 일반 사용자용 권장 진입점은 위 Custom GPT입니다.
