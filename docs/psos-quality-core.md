# PSOS Quality Core

메인 Codex 기반 PSOS에 요청별 완료 조건과 결과 검증을 추가하는 범용 품질 계층이다. 특정 상품·차트·댓글 규칙을 코어에 넣지 않는다.

## 실행 흐름

```text
사용자 요청
→ Goal Ledger와 route
→ Result Contract 생성
→ 기존 PSOS 실행
→ 계약 검증
→ 비파괴 경로만 빠진 항목 1회 보충
→ Evidence Bundle 생성
→ 사용자 검토용 기록 저장
```

## 포함 범위

- Result Contract 생성·검증·SHA-256 기록
- URL, evidence, artifact, receipt, visual 참조의 기계적 하드게이트
- 최소 출처 수와 결론-출처 연결 검사
- `partial`, `blocked`, `no_winner` 실패 정책
- CODE·PROJECT 자동 재실행 금지
- 결과·출처·파일·receipt를 묶는 Evidence Bundle
- `유지 / 의심 / 제외` 판정 데이터와 원본 보존형 revision 문맥
- 단순 DIRECT 요청의 추가 모델 호출과 빈 bundle 생략

## 실행

```powershell
python -B .\scripts\problem_solving_os_quality_runtime.py --request "해결할 요청"
```

## 경계

- canonical `problem_solving_os.py`를 대체하지 않는 얇은 진입점이다.
- 브라우저 갤러리와 외부 사진 수집은 별도 시각 근거 PR에 둔다.
- PROMPT 생성 trace·causal audit·ablation은 별도 프롬프트 진단 PR에 둔다.
- 기존 backup·workspace receipt·rollback·정책 생명주기는 유지한다.
