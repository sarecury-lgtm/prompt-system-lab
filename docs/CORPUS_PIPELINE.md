# Corpus Upgrade Pipeline

사용자가 실행할 명령은 하나다.

```bash
python scripts/corpus_pipeline.py run --strategy pattern-gaps --limit 10
```

이 명령은 다음 작업을 자동으로 수행한다.

1. 근거가 약한 패턴을 보강할 자료를 선택한다.
2. 첫 번째 비대화형 Codex 세션이 원문을 열고 Pattern lesson을 작성한다.
3. 작성 맥락을 공유하지 않는 두 번째 Codex 세션이 원문을 다시 열어 근거 관계, reusable move, 과장과 누락을 독립적으로 검토한다.
4. 스크립트가 URL, ID, 필수 필드, 중복, 상태 전이와 evidence note를 결정적으로 검사한다.
5. 두 모델의 판정이 일치하고 모든 검사를 통과한 항목만 manifest와 lesson 초안에 반영한다.
6. 나머지는 `deferred`로 기록하고 다음 배치에서는 건너뛴다.

같은 URL은 오류가 아니라 검토 신호다. 서로 다른 프롬프트·규칙·사례는 `distinct`로 유지하고, 실제 근거가 같으면 하나를 `canonical`로 두고 나머지를 `alias`로 연결한다. 자동 판정이 어려운 그룹은 `deferred`로 건너뛴다.

현재 `pattern-gaps` 전략은 번호순이 아니라 다음 미충족 목표를 순서대로 고른다: Structured Output / Extraction 직접 근거, Grounded Research 초안의 최종 자동 검증, Defensive Jailbreak Analysis 보류 원인 재검토. 이미 자동 검증 근거가 생긴 패턴은 선택하지 않으며 세 패턴이 모두 충족되면 빈 배치를 반환한다.

실행 기록은 `reports/corpus-pipeline-runs/<batch-id>/`에 남는다. 여기에는 두 Codex 세션의 프롬프트·원시 결과·로그, 자동 결정, 보류 사유, apply 결과, 전체 validation과 쉬운 요약이 포함된다. 패턴 인덱스는 계속 후보 파일까지만 생성하며 자동 확정하지 않는다.
