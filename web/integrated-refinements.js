(() => {
  const requestField = document.querySelector("#renderer-goal");
  const preview = document.querySelector("#integrated-instruction-preview");
  if (!requestField || !preview) return;

  const originalRule =
    "8. final_prompt는 JSON 문자열이어야 하므로 실제 줄바꿈은 \\n으로 이스케이프한다.";
  const refinedRules = [
    "8. 사용자가 요구하지 않았고 근거도 정의되지 않은 신뢰도 등급·점수·백분율을 출력 형식에 추가하지 않는다.",
    "9. 신규 진입 판단과 보유 포지션 관리처럼 서로 다른 판단 축을 하나의 선택지 목록에 섞지 말고 필요한 경우 각각 분리한다.",
    "10. 누락된 기간·성향·기준을 처리할 때 임의의 고정값을 넣지 않는다. 제공된 입력 구성을 바탕으로 추정하고 추정임을 밝히거나, 결과가 크게 달라질 때만 질문한다.",
    "11. final_prompt는 JSON 문자열이어야 하므로 실제 줄바꿈은 \\n으로 이스케이프한다.",
  ].join("\n");

  function refinePreview() {
    if (!preview.value || preview.value.includes("근거도 정의되지 않은 신뢰도")) return;
    preview.value = preview.value.replace(originalRule, refinedRules);
  }

  requestField.addEventListener("input", () => window.setTimeout(refinePreview, 0));
  window.setTimeout(refinePreview, 0);
  window.localStorage.removeItem("psos-blind-comparison-map");
})();
