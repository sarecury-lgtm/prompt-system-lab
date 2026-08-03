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

  window.PSOSManualProtocol = Object.freeze({
    ...base,
    inferRoute,
    buildJobPacket,
  });
})();
