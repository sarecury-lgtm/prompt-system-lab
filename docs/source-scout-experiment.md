# Source Scout Experiment

본격 조사 전에 답이 가장 많이 압축된 정보 생태계를 작은 예산으로 정찰하는 독립 실험이다. 메인 PSOS와 동적 루프 UI에는 아직 연결하지 않는다.

```text
사용자 요청
→ 최대 4회로 커뮤니티·판매처·1차 자료·재사용 목록·일반 웹을 비교
→ 코드가 정보 밀도와 접근성을 계산
→ 주력 정보원과 필요한 보조 정보원 선택
→ 그 뒤에만 본 조사 실행
```

## 실행

```powershell
& 'C:\Users\jeong\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B 'C:\Users\jeong\prompt-system-lab\scripts\problem_solving_source_scout_experiment.py' --request '해결할 요청'
```

앞선 대화가 정보원 선택에 영향을 줄 때만 `--context-file`을 추가한다. 기본 검색 상한은 4회이며 `--max-searches 2`부터 `6`까지만 허용한다.

## 선택 경로

- `COMMUNITY_REUSE`: 커뮤니티의 반복된 구체적 경험으로 거의 끝낼 수 있음
- `COMMUNITY_THEN_VERIFY`: 커뮤니티에서 후보를 얻고 현재 가격·재고나 1차 사실만 검증
- `MARKET_SCAN`: 판매 중인 목록과 실구매 조건을 직접 구조화
- `PRIMARY_SOURCE`: 공식 원문이나 1차 자료가 가장 빠름
- `REUSE_EXISTING`: 기존 제품·프로젝트·데이터를 먼저 검토
- `BROAD_RESEARCH`: 특정 정보원에 답이 압축되어 있지 않음
- `MULTI_SOURCE_RESEARCH`: 정찰에서 뚜렷한 승자가 없음
- `NO_EXTERNAL_RESEARCH`: 외부 조사가 필요하지 않음

## 판정 원칙

모델은 최종 경로를 직접 정하지 않고 정보원별 관찰만 반환한다. 실행기가 구체성, 최신성, 행동 가능성, 접근성, 실제 단서 수를 계산해 주력 경로를 고른다. 막힌 사이트는 감점하고 우회에 시간을 쓰지 않는다.

생성 파일:

- `source-scout-state.json`: 원 정찰 자료, 점수, 선택 경로, 시간과 토큰
- `result.md`: 사람이 빠르게 확인할 요약
- `source-scout-request.md`, `source-scout-output.json`, `source-scout.log`: 모델 호출 기록
