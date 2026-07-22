# V0.1 Runtime Result

## 현재 테스트 상태

- 기준선: 기존 전체 테스트 51/51 통과
- 구현 후: 전체 테스트 59/59 통과
- 실행 명령: `python -m unittest discover -s tests -v`

## 실제 실행 명령

```powershell
python scripts/prompt_runtime.py "요청을 여기에 입력하세요"
python scripts/prompt_runtime.py "문맥을 바탕으로 계획을 작성해 주세요." --context .\notes.txt
python scripts/prompt_runtime.py "결정 사항을 JSON으로 추출해 주세요." --output .\out\prompt.txt
```

## 입력과 출력 예시

- 입력: `세 가지 선택지를 비용과 위험 기준으로 표로 비교해 주세요.`
- 화면 출력: `모드: pattern-only`, 선택 이유, 사용 패턴, active source 없음, fallback 이유, 두 결과 경로
- 최종 프롬프트: `runtime-results/<실행시각>/prompt.txt`
- 상세 기록: `runtime-results/<실행시각>/routing.json`

## 생성·수정한 파일

- 생성: `.gitignore`
- 생성: `QUICKSTART.md`
- 생성: `scripts/prompt_runtime.py`
- 생성: `tests/test_prompt_runtime.py`
- 생성: `RESULT_INBOX/V0_1_RUNTIME_RESULT.md`
- 기존 라우터, active 정책, 패턴, corpus, Entity-Normalized Comparison 자료는 수정하지 않음

## smoke test 5건 결과

| 유형 | 종료 | 최종 모드 | 프롬프트/기록 | 관련 없는 active |
|---|---:|---|---|---|
| 간단한 재작성 | 0 | baseline | 생성/생성 | 없음 |
| 외부 조사용 프롬프트 | 0 | pattern-only | 생성/생성 | 없음 |
| 복잡한 비교 작업 | 0 | pattern-only | 생성/생성 | 없음 |
| 구조화된 산출물 요청 | 0 | pattern-only | 생성/생성 | 없음 |
| 파일 또는 코드 관련 요청 | 0 | pattern-only | 생성/생성 | 없음 |

추가 positive control인 반복 평가 실행기 요청은 허용 목록의 PR065 하나만 선택하고 active를 유지했다.

## fallback 검증 결과

- active 생성 강제 실패 → pattern-only: 통과
- pattern-only 생성 강제 실패 → baseline: 통과
- 존재하지 않는 문맥 파일 → 오류 기록 후 최종 프롬프트 반환: 통과
- 라우팅 기록 저장 실패 → 저장 오류 반환, 이미 생성된 최종 프롬프트 유지: 통과
- 비교 요청의 active 후보 부재 → pattern-only fallback과 이유 기록: 통과

## 커밋과 태그

- 커밋: `Create v0.1 prompt runtime`
- 태그: 생성하지 않음. 실행판이 의존하는 기존 라우터·정책·테스트가 현재 미추적 사용자 작업이므로, 새 파일만 담은 커밋에 릴리스 태그를 붙이면 깨끗한 checkout에서 실행판이 완전하지 않다.

## 현재 바로 가능한 작업

- 요청 문자열 하나로 최종 프롬프트와 상세 JSON 기록 생성
- UTF-8 문맥 파일 여러 개 추가
- 결과 경로 지정 또는 기본 시각별 경로 사용
- baseline/pattern-only/active 선택과 단계별 fallback
- 로컬 현재 작업공간에서 전체 테스트와 5종 smoke test 재현

## 아직 불가능한 작업

- 생성된 최종 프롬프트가 요구하는 실제 조사·코드 작업의 자동 실행
- full corpus 자동 검색
- active source 두 개 이상 자동 사용
- 신규 자료 수집, 새 패턴, Entity-Normalized Comparison
- 현재 미추적 의존 파일을 제외한 깨끗한 Git checkout에서의 독립 실행 및 안전한 `v0.1-runtime` 태그
