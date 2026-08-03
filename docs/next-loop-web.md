# PSOS next-loop 품질 화면

기존 품질 화면을 유지하면서 조사형 요청에만 다음 루프를 선택적으로 사용한다.

```text
요청
→ 정보원 정찰
→ 후보 작업대
→ 사용자 한 줄 교정
→ 재정렬 / 필터 / 부분 재조사 / 검증
→ 완료 또는 추가 교정
```

## 실행

```powershell
python -B scripts/problem_solving_quality_next_loop_web.py --open-browser chrome
```

또는 저장소 루트의 `start-psos-next-loop.cmd`를 실행한다.

## 화면 사용

1. 평소처럼 요청을 입력한다.
2. `후보 교정 루프`를 선택한다.
3. 첫 실행은 정보원 정찰과 후보 작업대 생성 후 멈춘다.
4. 결과 아래에서 짧게 교정한다.
   - `candidate-002 제외`
   - `전부 비쌈`
   - `100g당 1000원 이하 더 찾아`
   - `candidate-001 현재 판매 여부 확인`
5. 기존 후보로 처리할 수 있으면 재검색하지 않고, 부족한 구간만 동적 루프로 넘긴다.

## 경계

- next-loop는 읽기 전용이다. 파일 변경 요청은 기존 품질 실행을 사용한다.
- next-loop 실행 기록은 canonical 품질 기록과 섞이지 않도록 `runs/next-loop-experiments/`에 둔다.
- 기존 `problem_solving_quality_web.py`는 fallback으로 남긴다.
- 이 화면에서 대표 작업 검증이 끝난 뒤 canonical 실행기로 교체할지 결정한다.

## 승격 전 확인

- 상품 구매: 후보 제외와 가격 상한 변경 후 부분 재조사
- 정보 조사: 공식 원문 우선으로 정찰 전략이 바뀌는지 확인
- 제작·설계: 기존 자산 후보를 보존한 채 접근법만 교정 가능한지 확인
- `awaiting_correction`과 `awaiting_information`이 최종 완료로 잘못 표시되지 않는지 확인
