(() => {
  if (typeof elements === "undefined" || typeof promptUi === "undefined") return;

  const STORAGE_KEY = "psos-chatgpt-manual-fallback";
  const LAST_RESPONSE_KEY = "psos-chatgpt-manual-last-response";
  const guide = document.querySelector("#workflow-guide");
  const guideActions = guide?.querySelector(".workflow-guide-actions");
  const errorPanel = document.querySelector("#error-result");
  if (!guide || !guideActions || !errorPanel) return;

  const routeLabels = {
    direct: "일반 해결",
    research: "최신 조사",
    candidate: "후보 비교",
    prompt: "프롬프트 제작",
    write: "파일 변경 보조",
  };

  function currentRequest(form = elements.form) {
    return form === promptUi.form
      ? promptUi.request.value.trim()
      : elements.request.value.trim();
  }

  function classify(request, form = elements.form) {
    if (form === promptUi.form) return "prompt";
    return window.PSOSWorkflowRouter?.classifyRequest(request) || "direct";
  }

  function routeInstructions(route) {
    if (route === "research") {
      return `최신 정보가 결과를 바꾸는 조사 요청이다.
- 웹 검색을 실제로 수행한다.
- 날짜·가격·판매 여부·규정처럼 변하는 사실은 출처와 확인 시점을 적는다.
- 확인한 사실과 추론을 구분한다.
- 자료가 충돌하면 어떤 근거를 더 신뢰했는지 설명한다.
- 최종적으로 사용자가 바로 판단할 수 있는 결론을 낸다.`;
    }
    if (route === "candidate") {
      return `추천·구매·비교 요청이다.
- 실제로 유효한 후보 3~7개만 남긴다.
- 각 후보에 candidate-001 형식의 고정 ID를 부여한다.
- 이름, 출처 링크, 확인된 속성, 장점, 위험, 아직 확인할 점을 적는다.
- 첫 답변에서는 후보 작업대까지만 제시하고 사용자의 짧은 교정을 기다린다.
- 다음 대화에서는 ID와 확인된 정보를 유지하며 필요한 부분만 수정·재조사한다.`;
    }
    if (route === "prompt") {
      return `다른 AI가 바로 실행할 최종 프롬프트를 만드는 요청이다.
- 상위 목적, 고정 조건, 실제 수행 절차와 완료 조건을 내부적으로 정리한다.
- 같은 의미를 반복하지 않는다.
- 작성 과정이나 내부 구조 설명은 출력하지 않는다.
- 복사해 바로 사용할 수 있는 프롬프트 본문 하나만 제공한다.`;
    }
    if (route === "write") {
      return `일반 ChatGPT에서 수행하는 파일 작업이다.
- 사용자가 첨부하거나 붙여 넣은 파일을 기준으로 작업한다.
- 기존 기능을 빠뜨리지 않고 요청한 부분만 수정한다.
- 필요한 파일이 없으면 정확히 어떤 파일이 필요한지만 말한다.
- 가능하면 전체 교체 파일 또는 적용 가능한 통합 diff를 제공한다.
- 실제 로컬 적용이 끝났다고 주장하지 않는다.`;
    }
    return `현재 대화와 제공된 자료로 요청을 직접 해결한다.
- 가장 가능성 높은 의도를 먼저 잡고 진행한다.
- 결론을 바꾸는 정보가 부족할 때만 질문한다.
- 설명만 하지 말고 바로 쓸 수 있는 결과를 완성한다.
- 사실, 사용자 제공 정보와 추론을 섞지 않는다.`;
  }

  function buildInitialPacket(route, request) {
    return `당신은 Personal Problem-Solving OS의 수동 실행 엔진이다.

${routeInstructions(route)}

[공통 원칙]
1. 사용자의 질문을 다른 문제로 바꾸지 않는다.
2. 사용자 정의, 대상 범위, 주체, 시간 순서와 고정 조건을 보존한다.
3. 그럴듯한 일반론보다 실제 요청의 병목을 해결한다.
4. 검증하지 않은 사실을 확신하지 않는다.
5. 내부 추론 과정은 노출하지 않는다.

[사용자 요청]
${request}`;
  }

  function buildContinuationPacket(route, request, previous, correction) {
    const preservation = route === "candidate"
      ? "후보 ID와 이미 확인된 정보는 유지하고, 제외한 후보를 다시 살리지 않는다."
      : "이미 맞는 내용과 구조는 보존한다.";
    return `당신은 Personal Problem-Solving OS의 수동 후속 실행 엔진이다.

이전 결과를 처음부터 새로 만들지 말고 사용자의 교정을 필요한 부분에만 반영한다.
${preservation}

[원래 요청]
${request}

[이전 결과]
${previous}

[사용자 교정]
${correction}

[출력]
교정이 반영된 새 결과만 제시한다. 메타 설명은 최소화한다.`;
  }

  const toggle = document.createElement("label");
  toggle.className = "workflow-manual-toggle";
  toggle.innerHTML = `
    <input id="chatgpt-manual-enabled" type="checkbox">
    <span>
      <strong>Codex 없이 사용</strong>
      <small>일반 ChatGPT에 보낼 지시문을 만들고 결과를 다시 붙여 넣습니다.</small>
    </span>
  `;
  guideActions.insertBefore(toggle, guideActions.lastElementChild);
  const toggleInput = toggle.querySelector("#chatgpt-manual-enabled");

  const panel = document.createElement("section");
  panel.id = "chatgpt-manual-panel";
  panel.className = "chatgpt-manual-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="chatgpt-manual-heading">
      <div>
        <span class="workflow-kicker">일반 ChatGPT 수동 실행</span>
        <h3>복사해 보내고, 받은 답변을 다시 붙여 넣습니다.</h3>
        <p id="chatgpt-manual-summary"></p>
      </div>
      <span id="chatgpt-manual-route" class="workflow-badge"></span>
    </div>
    <label class="field-label">
      <span>ChatGPT에 보낼 실행 지시문</span>
      <textarea id="chatgpt-manual-packet" rows="14" readonly></textarea>
    </label>
    <div class="chatgpt-manual-actions">
      <span id="chatgpt-manual-status" role="status" aria-live="polite"></span>
      <div class="approval-actions">
        <button id="chatgpt-manual-copy" type="button" class="secondary-button">지시문 복사</button>
        <button id="chatgpt-manual-open" type="button" class="secondary-button">복사하고 ChatGPT 열기</button>
      </div>
    </div>
    <label class="field-label">
      <span>ChatGPT에서 받은 답변</span>
      <textarea id="chatgpt-manual-response" rows="12" placeholder="일반 ChatGPT의 답변을 여기에 붙여 넣으세요."></textarea>
    </label>
    <div class="chatgpt-manual-actions">
      <span>붙여 넣은 답변은 현재 PSOS 결과 화면에서 볼 수 있습니다.</span>
      <button id="chatgpt-manual-save" type="button">결과로 저장</button>
    </div>
    <div class="chatgpt-manual-followup">
      <label class="field-label">
        <span>결과를 보고 바꿀 점</span>
        <textarea id="chatgpt-manual-correction" rows="3" placeholder="예: candidate-002 제외 / 가격을 더 중요하게 / 이 부분만 다시 검증"></textarea>
      </label>
      <button id="chatgpt-manual-followup-button" type="button" class="secondary-button">후속 지시문 만들기</button>
    </div>
  `;
  guide.insertAdjacentElement("afterend", panel);

  const packet = panel.querySelector("#chatgpt-manual-packet");
  const response = panel.querySelector("#chatgpt-manual-response");
  const correction = panel.querySelector("#chatgpt-manual-correction");
  const routeBadge = panel.querySelector("#chatgpt-manual-route");
  const summary = panel.querySelector("#chatgpt-manual-summary");
  const status = panel.querySelector("#chatgpt-manual-status");
  let activeRoute = "direct";
  let activeRequest = "";

  function refreshPacket(form = elements.form) {
    activeRequest = currentRequest(form);
    activeRoute = classify(activeRequest, form);
    routeBadge.textContent = routeLabels[activeRoute] || activeRoute;
    routeBadge.dataset.route = activeRoute;
    summary.textContent = activeRequest
      ? `${routeLabels[activeRoute] || activeRoute} 작업을 일반 ChatGPT에서 이어갑니다.`
      : "요청을 입력하면 작업 종류에 맞는 지시문을 만듭니다.";
    packet.value = activeRequest ? buildInitialPacket(activeRoute, activeRequest) : "";
  }

  function setEnabled(enabled, reason = "") {
    const value = Boolean(enabled);
    toggleInput.checked = value;
    panel.hidden = !value;
    document.body.classList.toggle("chatgpt-manual-enabled", value);
    window.localStorage.setItem(STORAGE_KEY, String(value));
    if (value) {
      refreshPacket();
      if (reason) status.textContent = reason;
    }
  }

  async function copyPacket(openChatGPT = false) {
    if (!packet.value.trim()) {
      status.textContent = "먼저 요청을 입력해 주세요.";
      return;
    }
    try {
      await navigator.clipboard.writeText(packet.value);
      status.textContent = "지시문을 복사했습니다.";
      if (openChatGPT) {
        const opened = window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
        if (!opened) status.textContent = "복사했지만 팝업이 차단되었습니다.";
      }
    } catch (_error) {
      status.textContent = "자동 복사에 실패했습니다. 직접 선택해 복사해 주세요.";
    }
  }

  function saveManualResult() {
    const text = response.value.trim();
    if (!text) {
      response.focus();
      return;
    }
    window.localStorage.setItem(LAST_RESPONSE_KEY, text);
    showCompleted({
      run_id: `manual-chatgpt-${Date.now()}`,
      route: `MANUAL CHATGPT · ${routeLabels[activeRoute] || activeRoute}`,
      execution_status: "completed",
      result_markdown: text,
      artifacts: [],
      evidence: [],
      limitations: ["일반 ChatGPT에서 수동으로 실행하고 붙여 넣은 결과입니다."],
      workspace_receipt: null,
      workspace_rollback: null,
    });
    status.textContent = "붙여 넣은 답변을 결과로 저장했습니다.";
  }

  function makeFollowup() {
    const previous = response.value.trim() || window.localStorage.getItem(LAST_RESPONSE_KEY) || "";
    const change = correction.value.trim();
    if (!previous) {
      response.focus();
      status.textContent = "먼저 이전 ChatGPT 답변을 붙여 넣어 주세요.";
      return;
    }
    if (!change) {
      correction.focus();
      status.textContent = "바꿀 점을 짧게 입력해 주세요.";
      return;
    }
    packet.value = buildContinuationPacket(activeRoute, activeRequest, previous, change);
    status.textContent = "이전 결과를 보존하는 후속 지시문을 만들었습니다.";
    packet.focus();
    packet.select();
  }

  document.addEventListener("submit", (event) => {
    if (!toggleInput.checked) return;
    if (event.target !== elements.form && event.target !== promptUi.form) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    refreshPacket(event.target);
    panel.hidden = false;
    status.textContent = "지시문을 ChatGPT에 보내고 답변을 아래에 붙여 넣으세요.";
    packet.scrollIntoView({ behavior: "smooth", block: "center" });
  }, true);

  toggleInput.addEventListener("change", () => setEnabled(toggleInput.checked));
  elements.request.addEventListener("input", () => {
    if (toggleInput.checked) refreshPacket();
  });
  promptUi.request.addEventListener("input", () => {
    if (toggleInput.checked && selectedEngineMode() === "integrated") {
      refreshPacket(promptUi.form);
    }
  });
  panel.querySelector("#chatgpt-manual-copy").addEventListener("click", () => copyPacket(false));
  panel.querySelector("#chatgpt-manual-open").addEventListener("click", () => copyPacket(true));
  panel.querySelector("#chatgpt-manual-save").addEventListener("click", saveManualResult);
  panel.querySelector("#chatgpt-manual-followup-button").addEventListener("click", makeFollowup);

  const fallbackButton = document.createElement("button");
  fallbackButton.type = "button";
  fallbackButton.className = "secondary-button chatgpt-error-fallback";
  fallbackButton.textContent = "일반 ChatGPT로 계속";
  fallbackButton.hidden = true;
  errorPanel.appendChild(fallbackButton);
  fallbackButton.addEventListener("click", () => {
    setEnabled(true, "Codex 실행 대신 일반 ChatGPT용 지시문을 만들었습니다.");
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function updateErrorFallback() {
    const message = String(elements.errorMessage.textContent || "");
    const unavailable = /(codex|usage|quota|credit|capacity|rate.?limit|한도|용량|사용량|크레딧|할당량)/i.test(message);
    const shouldHide = elements.error.hidden || !unavailable;
    if (fallbackButton.hidden !== shouldHide) {
      fallbackButton.hidden = shouldHide;
    }
  }

  new MutationObserver(updateErrorFallback).observe(errorPanel, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  new MutationObserver(updateErrorFallback).observe(elements.errorMessage, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  response.value = window.localStorage.getItem(LAST_RESPONSE_KEY) || "";
  setEnabled(window.localStorage.getItem(STORAGE_KEY) === "true");
  updateErrorFallback();
  window.PSOSManualChatGPT = Object.freeze({
    buildInitialPacket,
    buildContinuationPacket,
    setEnabled,
  });
})();
