# Dynamic Loop Experiment

이 실험은 첫 목표 해석 하나가 전체 검색을 지배하지 않도록 다음 과정을 분리한다.

```text
임시 본질 파악 ─┐
                ├─ 질문 게이트 → 행동 하나 → 독립 평가
독립 열린 탐색 ─┘                         ↓
                              STOP / CHANGE / ASK
```

메인 PSOS 동작을 바꾸지 않으며, 기본적으로 한 번만 실질적인 방법 변경을 허용한다.

## 실행

```powershell
& 'C:\Users\jeong\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B 'C:\Users\jeong\prompt-system-lab\scripts\problem_solving_dynamic_loop_experiment.py' --request '해결할 요청'
```

요청이 앞선 대화를 가리키면 관련 대화 부분을 `--context-file`로 함께 전달한다. 이 맥락은 본질 파악·질문·행동·검증에는 쓰지만, 다양성을 위한 독립 열린 탐색에는 전달하지 않는다.

외부 터미널처럼 질문에 답할 수 있는 환경에서는 실행 중 최대 세 가지 질문을 표시한다. 자동 실행에서는 필요한 답을 JSON으로 제공할 수 있다.

```json
{
  "purpose": "구이용",
  "skin_preference": "오겹살도 괜찮음"
}
```

```powershell
& 'C:\Users\jeong\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B 'C:\Users\jeong\prompt-system-lab\scripts\problem_solving_dynamic_loop_experiment.py' --request '해결할 요청' --answers-json 'C:\path\answers.json'
```

질문에서 멈춘 실행은 같은 폴더를 재개한다. 앞서 수행한 본질 파악과 열린 탐색은 다시 호출하지 않는다.

```powershell
& 'C:\Users\jeong\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B 'C:\Users\jeong\prompt-system-lab\scripts\problem_solving_dynamic_loop_experiment.py' --resume-run 'C:\Users\jeong\prompt-system-lab\runs\dynamic-loop-experiments\dynamic-example' --answers-json 'C:\path\answers.json'
```

현재 PSOS 전체 실행과 블라인드 비교 파일까지 만들려면 `--compare-baseline`을 추가한다. 결과의 실제 매핑은 `blind-map.json`에만 저장된다.

## 생성 파일

- `dynamic-state.json`: 본질 가설, 열린 탐색, 질문, 행동, 평가 기록
- `result.md`: 사용자가 비교할 최종 결과 또는 답이 필요한 질문
- 각 단계의 `*-request.md`, `*-output.json`, `*.log`: 감사 가능한 모델 호출 기록
- 비교 모드의 `result-A.md`, `result-B.md`: 이름을 가린 비교 결과

## 실험 규칙

- 열린 탐색은 본질 파악 결과를 받지 않고 사용자 원문만 본다.
- 완료 검증에 실패한 `partial` 결과는 추천문처럼 노출하지 않고 미완료 경고와 함께 저장한다.
- 열린 탐색은 넓게 보되 검색 6회, 관찰 8개 등 작은 상한 안에서 행동 지형만 만든다.
- 사용자 질문은 답이 실제 행동을 바꾸고 관찰 가능한 차이로 연결될 때만 한다.
- 정보는 중요성·관찰 가능성·구분력이 있을 때만 최종 판단에 사용한다.
- `CHANGE`는 정보원·도구·대상·방법·검증 중 하나를 실제로 바꿔야 한다.
- 동적 결과가 반복 과제에서 단일 실행보다 낫다는 증거가 생기기 전에는 메인 UI에 통합하지 않는다.
