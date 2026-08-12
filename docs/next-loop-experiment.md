# PSOS next-loop experiment

이 실험은 기존 `source_scout`와 `dynamic_loop`를 영속적인 후보 작업대로 연결한다.

```text
사용자 요청
→ 정보원 정찰
→ 후보 작업대
→ 사용자 짧은 교정
→ 재정렬·필터 또는 부분 재조사
→ 후보/완료 검증
→ 최종 결과
```

## 핵심 차이

정보원 정찰에서 나온 구체적 단서는 곧바로 최종 추천이 되지 않는다. `needs_check` 후보로 저장하고, 사용자가 짧게 쳐낸 뒤 필요한 작업만 수행한다.

- 후보 제외: `RERANK` — 새 검색 없이 로컬 상태만 변경
- 조건 변경: `FILTER` — 알려진 후보 속성으로 먼저 필터링
- 기존 데이터로 판단 불가: `PARTIAL_RESEARCH`
- 범위 확장·추가 후보 요청: `PARTIAL_RESEARCH`
- 특정 후보 확인: `VERIFY_CANDIDATE`
- 현재 후보로 결론 진행: `VERIFY_COMPLETION`

자연어 교정에서 모델은 교정 유형과 대상을 구조화할 뿐이다. 실제 행동 선택과 상태 변경은 코드가 담당한다.

## 정찰 결과 재사용

`source_scout` 결과는 기존 동적 루프의 `scan` 계약으로 변환된다.

- probe 검색어 → `vocabulary`
- concrete lead → `adjacent_possibilities`
- 정보원 신호 → `observations`
- 정찰 한계 → `source_gaps`

따라서 next-loop는 `dynamic-open-scan`을 다시 실행하지 않는다.

## 실행

```powershell
python scripts/problem_solving_next_loop_experiment.py `
  --request "온라인 삼겹살 후보를 찾아줘" `
  --run-id pork-next-loop
```

후보 작업대에서 재개:

```powershell
python scripts/problem_solving_next_loop_experiment.py `
  --resume runs/next-loop-experiments/pork-next-loop `
  --correction "전부 비싸. 100g당 1000원 이하를 더 찾아"
```

구조화된 교정 JSON은 `--correction-file`로 전달할 수 있다.

## 현재 범위

- 아직 기본 `run_quality_request()` 경로가 아닌 독립 실험기다.
- 정찰 단서의 도메인별 속성 추출은 아직 없다.
- 메인 UI의 교정 입력과 `awaiting_correction` 화면은 아직 없다.
- 실제 승격 전 저장소 전체 테스트와 대표 작업 3종 검증이 필요하다.

## 승격 조건

1. 새 조사 없이 처리되는 로컬 교정 1건
2. 기존 후보를 보존하는 부분 재조사 1건
3. partial 결과를 최종 결과로 잘못 승격하지 않는 완료 검증 1건
