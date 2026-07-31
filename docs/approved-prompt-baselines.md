# 승인 PROMPT baseline

검증에서 이긴 프롬프트를 다음 생성의 출발점으로 재사용하기 위한 보수적 레지스트리다.

## 원칙

- 승인된 프롬프트만 `approved-prompts/registry.json`에 등록한다.
- 등록 파일은 SHA-256으로 고정한다.
- 요청 문구가 명시된 `all_terms`와 `any_terms`를 만족할 때만 선택한다.
- 여러 자산이 동시에 맞거나 매칭이 모호하면 아무것도 선택하지 않는다.
- 승인 baseline은 Prompt Build Brief보다 먼저 Compiler baseline의 `final_prompt`를 대체한다.
- Brief는 승인 baseline의 누락·충돌만 패치하며, 승인 자산 자체를 자동 승격·교체하지 않는다.

현재 승인 자산은 차트 매매 판단 프롬프트 하나다. 댓글·상품 프롬프트는 적용 검증 전이므로 등록하지 않았다.

## 승인 baseline 수동 검증

Codex 없이 여기 ChatGPT에서 검증할 때:

```powershell
python -B .\scripts\problem_solving_prompt_approved_patch_review.py prepare
```

패치 후보가 있으면:

```powershell
python -B .\scripts\problem_solving_prompt_approved_patch_review.py prepare `
  --patch-dir ".\patches"
```

차트 사례는 승인된 `chart-trade-plan.md`를 baseline으로 사용한다. 댓글·상품은 승인 자산이 없으므로 기존 Compiler baseline을 사용한다.

## 승인 baseline 품질 런타임

기존 품질 런타임을 그대로 두고 승인 자산을 사용하는 별도 진입점을 제공한다.

```powershell
python -B .\scripts\problem_solving_os_approved_quality_runtime.py `
  --request "다중 시간대 차트 매매 프롬프트를 만들어줘"
```

이 진입점의 CLI 엔진은 기존 품질 런타임과 동일하다. 승인 자산 선택 기능 자체는 모델을 호출하지 않지만, 전체 PSOS 실행은 기존 엔진 설정을 따른다.

## 새 자산 등록 조건

1. 같은 실제 입력에서 기존 baseline과 후보를 적용한다.
2. 후보 정체를 숨긴 채 평가한다.
3. 패치 후보만 명확히 선호되고 치명적 실패가 없어야 한다.
4. 동률이나 무승부면 baseline을 유지한다.
5. 승인 후 프롬프트 파일과 해시, 근거 요약을 registry에 기록한다.
