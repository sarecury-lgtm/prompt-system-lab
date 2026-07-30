# PSOS Quality Layer

메인 PSOS 실행 결과에 요청별 완료 조건, 결과 검증, 제한된 보충 실행, 사용자 근거 검토를 추가하는 실험적 품질 계층이다.

수동 ChatGPT 브리지의 기능이 아니다. 기존 Codex 기반 PSOS와 로컬 작업실을 재사용한다.

## 실행

```powershell
cd "C:\Users\jeong\prompt-system-lab"
git switch agent/psos-quality-core
git pull
python -B .\scripts\problem_solving_quality_web.py --open-browser chrome
```

기본 주소는 `http://127.0.0.1:8765`다. 기존 PSOS 서버가 켜져 있다면 먼저 `Ctrl+C`로 종료한다.

CLI만 사용할 때는 다음 진입점을 쓴다.

```powershell
python -B .\scripts\problem_solving_os_quality_runtime.py --request "해결할 요청"
```

## 결과 흐름

```text
요청
→ Goal Ledger와 route
→ Result Contract 생성
→ 실제 실행
→ 계약 검증
→ 안전한 경로만 최대 1회 보충
→ Evidence Bundle 생성
→ PROMPT 경로이면 생성 단계 진단
→ 사용자 검토
→ 필요할 때 원본을 보존한 새 수정 실행
```

## PROMPT 생성 경로 진단

PROMPT가 포함된 실행은 최종 프롬프트를 바로 고치는 대신 다음 생성 단계를 비교한다.

```text
사용자 원문
→ Goal Ledger
→ Prompt Compiler baseline
→ PROMPT 실행기 입력
→ 최종 프롬프트
```

run 디렉터리에 다음 파일이 생성된다.

```text
prompt_generation_trace.json
prompt_generation_trace.md
```

기록에는 단계별 크기, 구간별 팽창, 최종 프롬프트의 유사 규칙 쌍, 평면 Ledger·additive baseline·중복 입력·형식 압력 신호가 포함된다. 이 진단은 기존 결과를 수정하지 않고 원인을 찾기 위한 자료만 남긴다.

기존 run을 따로 진단할 때는 다음을 사용한다.

```powershell
cd "C:\Users\jeong\prompt-system-lab"
python -B .\scripts\problem_solving_prompt_trace.py --run-dir .\runs\RUN_ID
```

구조적 원인과 비교 실험 기준은 `docs/prompt-generation-causal-audit.md`에 정리돼 있다.

## 웹 근거 검토

Evidence Bundle이 있는 실행을 열면 결과 아래에 `근거 직접 검토`가 표시된다.

각 사진·링크·파일·receipt에 다음 판정을 남길 수 있다.

- `유지`: 최종 결과에서 계속 사용한다.
- `의심`: 다시 확인하고, 확인할 수 없으면 단정을 낮춘다.
- `제외`: 최종 결론의 근거로 사용하지 않는다.

판정은 `evidence_review.json`에 저장되며 현재 `evidence_bundle.json`의 SHA-256과 묶인다. 오래된 화면이나 다른 실행의 판정을 섞으면 저장이 거부된다.

`판정 반영해 결과 수정`은 원래 `result.md`를 덮어쓰지 않는다. 부모 실행에 다음 기록을 남기고 별도의 자식 PSOS 실행을 만든다.

```text
evidence_revision_context.md
evidence_revision_request.json
```

자식 실행은 `유지` 근거를 보존하고, `의심` 근거를 다시 확인하거나 표현을 약화하며, `제외` 근거와 그 근거에만 의존한 주장을 제거한다. 대체 URL·가격·후기·사진을 만들어서는 안 된다.

## 현재 경계

- PROMPT 진단은 구조와 반복을 추적하며, 프롬프트의 도메인 정확성 자체를 판정하지 않는다.
- 페이지를 돌아다니며 사진을 새로 수집하는 기능은 아직 없다. 실행 결과나 evidence에 들어온 사진만 검토한다.
- 근거를 후보별·주장별로 자동 연결하지 않고 우선 결과 전체에 연결한다.
- 외부 이미지 서버가 미리보기를 막으면 원본 링크로 직접 확인해야 한다.
- CODE·PROJECT는 중복 파일 변경 위험 때문에 계약 미충족 시 자동 보충 실행을 하지 않는다.
- 품질 계층은 아직 Draft PR의 별도 진입점이며 canonical `problem_solving_os.py`를 대체하지 않는다.
