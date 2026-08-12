(() => {
  const base = window.PSOSManualProtocol;
  if (!base) return;

  function inferRoute(request, externalHint = "") {
    const text = String(request || "").trim();
    const decisionAction = /(살까|매수|진입|매도|팔까|대기|회피|보유|손절|구매할까|사도 될까|해야 할까|어떻게 해야)/i.test(text);
    const broadSearch = /(추천|후보|여러|몇 개|찾아|골라|비교|가장 좋은|1위)/i.test(text);
    if (decisionAction && !broadSearch) return "DECISION";
    return base.inferRoute(text, externalHint);
  }

  function buildJobPacket(options = {}) {
    const routeHint = inferRoute(options.request, options.routeHint);
    return base.buildJobPacket({
      ...options,
      routeHint,
    });
  }

  function buildExecutionPrompt(packet) {
    const prompt = base.buildExecutionPrompt(packet);
    if (packet?.route_hint !== "WRITE") return prompt;
    return `${prompt}\n\n[WRITE 결과 계약]\n파일 변경이 필요하면 Result Envelope의 artifacts에 설명이 아니라 실제 전체 파일 내용을 넣는다.\n- 지원 action: create, replace\n- delete는 만들지 않는다.\n- 각 항목 형식: {"kind":"file_change","action":"create|replace","path":"저장소 상대 경로","content":"UTF-8 전체 파일 내용"}\n- 변경하지 않는 파일은 artifacts에 넣지 않는다.\n- 기존 파일을 replace할 때는 일부 조각이나 생략 표시가 아니라 완성된 전체 파일을 반환한다.\n- verification은 {"commands":[...]} 형식으로 반환한다. 허용되는 검사는 python -m py_compile, python -m unittest, node --check뿐이다.\n- 파일을 실제로 적용하거나 테스트했다고 주장하지 않는다. PSOS가 사용자 승인 후 로컬에서 적용·검사한다.\n- 결과 설명 속 코드블록은 파일 변경으로 간주되지 않으므로 반드시 artifacts 구조를 채운다.`;
  }

  window.PSOSManualProtocol = Object.freeze({
    ...base,
    inferRoute,
    buildJobPacket,
    buildExecutionPrompt,
  });
})();
