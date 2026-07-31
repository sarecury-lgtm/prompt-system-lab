# 차트 프롬프트 일괄 비교

같은 차트 이미지와 같은 사용자 문맥을 여러 프롬프트에 한 번씩 독립 적용하고, 결과를 A~H로 익명화해 다시 비교한다.

## 가장 간단한 사용법

한 폴더에 아래 네 파일을 둔다. 파일명 뒤의 `(1)` 같은 다운로드 중복 표시는 있어도 된다.

```text
current.md
without_raw_request.md
compact_ledger.md
single_build_brief.md
```

차트 이미지는 별도 폴더에 넣고 실행한다.

```powershell
python -B .\scripts\problem_solving_chart_prompt_batch.py `
  --prompt-dir "C:\Users\jeong\Downloads\chart-prompts" `
  --image-dir "C:\Users\jeong\Downloads\chart-images" `
  --context-file "C:\Users\jeong\Downloads\trade-context.md" `
  --open-report
```

`trade-context.md`는 없어도 된다. 보유 여부, 평균 진입가, 생각해 둔 손절·익절, 예상 보유 기간처럼 네 분석에 똑같이 전달할 정보만 적는다.

이미지를 개별 지정할 수도 있다.

```powershell
python -B .\scripts\problem_solving_chart_prompt_batch.py `
  --prompt-dir ".\chart-prompts" `
  --image ".\charts\weekly.png" `
  --image ".\charts\daily.png" `
  --image ".\charts\4h.png" `
  --context "현재 보유 중. 평균 진입가 00, 손절 후보 00." `
  --open-report
```

임의의 프롬프트 파일을 비교할 때는 `label=파일경로`로 지정한다.

```powershell
python -B .\scripts\problem_solving_chart_prompt_batch.py `
  --prompt "first=.\prompt-a.md" `
  --prompt "second=.\prompt-b.md" `
  --image-dir ".\charts"
```

## 실행 결과

기본 결과 위치:

```text
runtime-results/chart-prompt-comparison/<시간>/
```

주요 파일:

- `blind-report.md`: 프롬프트 이름이 가려진 A~H 분석과 자동 평가
- `report.md`: 마지막에 후보와 원래 프롬프트 이름을 공개한 최종 보고서
- `assessment.json`: 관찰 정확성, 시간대 종합, 결론 명확성, 계획 품질, 불확실성 처리, 형식 부담 평가
- `manifest.json`: 모델, reasoning, 모든 입력 SHA-256, 후보 매핑과 결과 경로
- `inputs/`: 실행 당시 프롬프트·차트·추가 문맥 복사본
- `candidates/`: 후보별 분석 원문
- `engine/`: 각 Codex 요청, 구조화 결과와 로그

## 비교 통제

- 모든 후보에 같은 모델과 reasoning effort를 사용한다.
- 웹 검색은 사용하지 않는다.
- 모든 후보와 평가자에 같은 이미지 복사본을 첨부한다.
- 각 프롬프트는 별도 `codex exec` 실행으로 처리한다.
- 평가자에게 원래 프롬프트 파일명과 변형명을 보여주지 않는다.
- 평가자도 원본 차트를 직접 받아, 보이지 않는 숫자·지표 생성 여부를 확인한다.
- 원본 프롬프트와 이미지에는 쓰지 않는다.

## 경계

이 평가는 한 번의 모델 실행에서 나타난 품질 차이다. 차이가 작으면 실행 변동일 수 있으므로 다른 차트 묶음에서도 반복해야 한다. 실제 매매 성과를 증명하는 실험은 아니며, 차트에서 근거를 충실히 읽고 실행 가능한 계획을 만드는 품질을 비교한다.
