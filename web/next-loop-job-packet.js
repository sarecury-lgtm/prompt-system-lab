(() => {
  if (
    typeof elements === "undefined" ||
    typeof requestJson !== "function" ||
    typeof setResultState !== "function" ||
    !window.PSOSManualProtocol
  ) return;

  const protocol = window.PSOSManualProtocol;
  const form = elements.form;
  const autoToggle = document.querySelector("#workflow-auto-enabled");
  const nextLoopToggle = document.querySelector("#next-loop-enabled");
  const titleNode = document.querySelector("#workflow-title");
  const detailNode = document.querySelector("#workflow-detail");
  const badgeNode = document.querySelector("#workflow-badge");
  if (!form || !autoToggle) return;

  const routeCopy = {
    DIRECT: {
      badge: "일반 해결",
      title: "요청을 끝까지 해결하고 최종 답만 보여줍니다.",
      detail: "중간 계획이나 작업대에서 멈추지 않고 바로 사용할 결과를 만듭니다.",
    },
    RESEARCH: {
      badge: "최신 조사",
      title: "현재 정보를 확인한 뒤 결론까지 냅니다.",
      detail: "검색 결과를 나열하지 않고 출처·확인 시점·판단을 하나의 답으로 연결합니다.",
    },
    DECISION: {
      badge: "행동 판단",
      title: "특정 대상에 대해 지금 할 행동 하나를 고릅니다.",
      detail: "가장 큰 반대 근거와 판단이 바뀌는 조건까지 포함해 결론을 냅니다.",
    },
    CANDIDATE: {
      badge: "비교·최종 선택",
      title: "후보를 검증하고 최종 1순위까지 고릅니다.",
      detail: "부적격 후보를 제거한 뒤 같은 기준으로 비교하고 후보 작업대에서 멈추지 않습니다.",
    },
  };

  function automaticEnabled() {
    return Boolean(autoToggle.checked) && !document.body.classList.contains("manual-v5-enabled");
  }

  function routeFor(request) {
    return protocol.inferRoute(String(request || ""));
  }

  function renderRoute(route) {
    const copy = routeCopy[route];
    if (!copy || !titleNode || !detailNode || !badgeNode) return;
    titleNode.textContent = copy.title;
    detailNode.textContent = copy.detail;
    badgeNode.textContent = copy.badge;
    badgeNode.dataset.route = route.toLowerCase();
  }

  function syncRecommendation() {
    if (!automaticEnabled()) return;
    renderRoute(routeFor(elements.request.value));
  }

  async function submitJobPacket(request, route) {
    window.clearTimeout(pollTimer);
    if (nextLoopToggle?.checked) {
      nextLoopToggle.checked = false;
      nextLoopToggle.dispatchEvent(new Event("change", { bubbles: true }));
    }
    elements.submit.disabled = true;
    setResultState("running");
    elements.runningTitle.textContent =
      route === "CANDIDATE"
        ? "후보를 검증하고 최종 선택을 만들고 있습니다."
        : route === "DECISION"
          ? "현재 행동 결론을 만들고 있습니다."
          : route === "RESEARCH"
            ? "최신 정보를 확인하고 결론을 만들고 있습니다."
            : "요청을 끝까지 해결하고 있습니다.";
    elements.runningDetail.textContent =
      "Goal Ledger, 조사·판단 절차와 완료 조건을 하나의 Job Packet으로 실행합니다.";

    try {
      const job = await requestJson("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          search_enabled: ["RESEARCH", "DECISION", "CANDIDATE"].includes(route),
          execution_mode: "job_packet",
        }),
      });
      activeJobId = job.job_id;
      window.sessionStorage.setItem(activeJobStorageKey, activeJobId);
      pollJob();
    } catch (error) {
      showError(error.message);
    }
  }

  document.addEventListener(
    "submit",
    (event) => {
      if (event.target !== form || !automaticEnabled()) return;
      const request = elements.request.value.trim();
      if (!request) return;
      const route = routeFor(request);
      if (!["DIRECT", "RESEARCH", "DECISION", "CANDIDATE"].includes(route)) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      renderRoute(route);
      submitJobPacket(request, route);
    },
    true,
  );

  elements.request.addEventListener("input", syncRecommendation);
  autoToggle.addEventListener("change", syncRecommendation);
  syncRecommendation();

  window.PSOSAutomaticJobPacket = Object.freeze({
    version: 1,
    routeFor,
    submit: submitJobPacket,
  });
})();
