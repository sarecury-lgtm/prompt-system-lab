# v0.3 ChatGPT-GitHub Runtime 결과

## 현재 테스트 상태

- 전체 unittest: 66건 통과
- runtime 생성 결과 재현성 검사: 통과
- 실제 Custom GPT 정상 요청: 5/5 최종 프롬프트 생성
- 관련 없는 active source 선택: 0/5
- 내장 bundle 일반 요청: 통과, GitHub 승인창 없음
- 명시적 GitHub 최신화 요청: Action 승인창 표시 확인

## 실제 실행 명령

- 일반 사용자: https://chatgpt.com/g/g-6a606afd43308191baea14153489e228-prompt-compiler
- 개발 검증: `python scripts/build_chatgpt_action_runtime.py`
- 전체 테스트: `python -m unittest discover -s tests -v`

## 입력과 출력 예시

입력:

```text
여러 영수증 텍스트에서 날짜, 판매처, 총액, 세금, 품목을 JSON으로 추출하고 없는 값은 null로 내게 하는 프롬프트를 만들어줘.
```

출력은 복사 가능한 완성 프롬프트와 다음 선택 기록으로 생성되었습니다.

```text
모드: pattern-only
사용 패턴: Structured output / extraction
active source: 없음
fallback: 아니요
```

## 생성·수정한 파일

- `runtime/CUSTOM_GPT_INSTRUCTIONS.md`
- `runtime/PROMPT_COMPILER_BUNDLE.md`
- `runtime/README.md`
- `runtime/catalog.json`
- `runtime/openapi.yaml`
- `runtime/patterns/*.json` 9개
- `runtime/active/*.json` 7개
- `runtime/protocols/global-response-v3.1.json`
- `scripts/build_chatgpt_action_runtime.py`
- `tests/test_chatgpt_action_runtime.py`
- `QUICKSTART.md`
- `RESULT_INBOX/V0_3_CHATGPT_GITHUB_RUNTIME_RESULT.md`

## smoke test 5건 결과

1. 간단한 재작성: 통과, baseline, 패턴 없음, active 없음
2. 외부 조사: 통과, pattern-only, Grounded research, active 없음
3. 복잡한 비교: 통과, pattern-only, Grounded research + Structured output / extraction, active 없음
4. 구조화 산출물: 통과, pattern-only, Structured output / extraction, active 없음
5. 파일·코드 작업: 통과, pattern-only, Coding-agent workflow, active 없음

모든 정상 시험에서 요청별로 새로 작성된 최종 프롬프트와 선택 이유가 표시되었습니다.

## fallback 검증 결과

- 생성기와 routing의 호출 실패 fallback은 자동 테스트에서 검증되었습니다.
- 실제 ChatGPT에서 Action 승인을 사용자가 거절하면 모델이 fallback을 작성하기 전에 해당 응답 자체가 중단됩니다. 이는 Custom GPT Action 승인 UI의 동작이므로 프롬프트 지침만으로 복구할 수 없습니다.
- 이 한계를 피하기 위해 일반 요청은 Action을 호출하지 않고 Custom GPT Knowledge의 내장 bundle을 사용하도록 변경했습니다.
- GitHub Action은 사용자가 최신 자료 확인을 명시한 경우에만 호출됩니다.
- 승인된 Action 호출 내부에서 card 적용이 실패하는 경우에는 지침상 active → pattern-only → baseline 순으로 내려갑니다.
- 최초 정상 시험에서는 ChatGPT 일시 오류 1건이 발생했으나 새 채팅 재시도로 정상 완료되었습니다.

## 커밋과 태그

- runtime 구현 커밋: `9b601f23b86061d253b30241ed45badd7d72d062`
- 브랜치: `codex/chatgpt-github-runtime`
- GitHub 원격 push 완료
- 문서 보완 커밋, PR, merge, tag는 이 문서가 포함된 최종 작업에서 기록합니다.

## 현재 바로 가능한 작업

- ChatGPT Plus 안에서 일반 문장으로 요청하고 요청별 완성 프롬프트 받기
- 승인창 없이 내장된 9개 검증 패턴과 7개 허용 active card 사용
- 원할 때만 GitHub main의 최신 catalog와 card 확인
- 모드, 이유, 사용 패턴, active source, fallback 기록 확인
- 생성된 프롬프트를 다른 AI에 복사해 사용
- API 키와 별도 API 과금 없이 사용

## 아직 불가능한 작업

- ChatGPT 대화만으로 GitHub 파일을 자동 수정·commit·push
- 명시적으로 시작한 Action 연결을 거절한 동일 응답에서 자동 fallback 출력
- 비공개 저장소를 별도 인증 없이 raw GitHub Action으로 읽기
- full corpus 자동 검색 및 Entity-Normalized Comparison
