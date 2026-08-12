(() => {
  if (
    typeof elements === "undefined" ||
    typeof promptUi === "undefined" ||
    typeof showCompleted !== "function"
  ) return;

  const STORAGE_KEY = "psos-chatgpt-manual-v3";
  const guide = document.querySelector("#workflow-guide");
  const guideActions = guide?.querySelector(".workflow-guide-actions");
  const errorPanel = document.querySelector("#error-result");
  if (!guide || !guideActions || !errorPanel) return;

  const routeLabels = {
    direct: "일반 해결",
    research: "최신 조사",
    decision: "단일 대상 판단",
    candidate: "후보 비교·최종 선택",
    prompt: "프롬프트 제작",
    write: "파일 변경 보조",
  };

  const state = {
    enabled: false,
    route: "direct",
    request: "",
    packet: "",
    response: "",
    correction: "",
    includeCurrentResult: false,
    attachmentNames: [],
  };

  function currentRequest(form = elements.form) {
    return form === promptUi.form
      ? promptUi.request.value.trim()
      : elements.request.value.trim();
  }

  function classify(request, form = elements.form) {
    if (form === promptUi.form) return "prompt";
    const text = String(request || "").trim();
    const decisionAction = /(살까|매수|진입|매도|팔까|대기|회피|보유|손절)/i.test(text);
    const oneTargetSignal = /(오늘|지금|내일|실적|차트|이 종목|이 제품|이거)/i.test(text);
    const broadSearch = /(추천|후보|여러|몇 개|찾아|골라|비교|가장 좋은|1위)/i.test(text);
    if (decisionAction && oneTargetSignal && !broadSearch) return "decision";
    return window.PSOSWorkflowRouter?.classifyRequest(text) || "direct";
  }

  function routeInstructions(route) {
    if (route === "research") {
      return `최신 정보가 판단을 바꾸는 조사 요청이다.
- 웹 검색을 실제로 수행하고 변동 가능한 사실에 확인 날짜와 출처를 붙인다.
- 자료를 나열하는 데서 끝내지 말고 사용자의 질문에 대한 결론을 먼저 제시한다.
- 확인한 사실, 불확실한 부분, 그에 따른 판단을 구분한다.
- 일부 근거가 부족해도 가능한 범위의 결론은 내리고 부족한 부분만 경고한다.`;
    }
    if (route === "decision") {
      return `이미 특정된 한 대상에 대해 행동을 결정하는 요청이다.
- 후보 목록이나 중간 작업대에서 멈추지 않는다.
- 매수·대기·회피, 구매·보류 등 요청에 맞는 행동 하나를 분명히 선택한다.
- 핵심 근거, 가장 큰 반대 근거, 판단이 바뀌는 조건을 함께 제시한다.
- 이벤트 직전 투자처럼 손절선이 무력화될 수 있는 위험은 별도로 설명한다.
- 결론을 못 내릴 정도가 아니면 사용자 정보 부족을 이유로 답을 회피하지 않는다.`;
    }
    if (route === "candidate") {
      return `여러 후보를 조사해 실제 선택까지 끝내는 요청이다.
- 정보원 페이지가 아니라 실제 종목·상품·장소·서비스를 후보로 삼는다.
- 거래 불가, 품절, 유동성 부족, 과도한 급등, 조건 불일치 같은 부적격 후보는 내부에서 제거한다.
- 검증할 가치가 있는 후보만 3~5개로 압축해 비교하고 순위를 매긴다.
- 최종 1순위 또는 현재 조건에서 우승자가 없다는 결론을 분명히 제시한다.
- 후보 작업대에서 멈추거나 사용자의 추가 교정을 기다리지 않는다.
- 핵심 근거, 위험, 선택이 바뀌는 조건을 최종 결론과 연결한다.`;
    }
    if (route === "prompt") {
      return `다른 AI가 바로 실행할 최종 프롬프트를 만드는 요청이다.
- 상위 목적, 고정 조건, 실제 수행 절차, 완료 조건을 내부적으로 정리한다.
- 같은 의미를 반복하지 않는다.
- 생성 과정이나 내부 구조 설명 없이 복사해 바로 쓸 최종 프롬프트만 제공한다.`;
    }
    if (route === "write") {
      return `일반 ChatGPT에서 파일 수정을 보조하는 요청이다.
- 사용자가 ChatGPT 대화에 첨부하거나 붙여 넣은 파일만 기준으로 작업한다.
- 기존 기능을 보존하면서 요청한 부분만 수정한다.
- 가능하면 전체 교체 파일이나 적용 가능한 통합 diff를 제공한다.
- 실제 로컬 파일을 직접 수정했다고 주장하지 않는다.`;
    }
    return `현재 대화와 제공 자료로 요청을 직접 해결한다.
- 가장 가능성 높은 의도를 잡고 불필요한 중간 절차 없이 결과를 완성한다.
- 결론을 바꾸는 정보가 부족할 때만 질문한다.
- 사실, 사용자 제공 정보, 추론을 구분한다.
- 설명만 하지 말고 사용자가 바로 쓸 수 있는 답을 제시한다.`;
  }

  function stripAttachmentBlock(request) {
    const text = String(request || "");
    const markerIndex = text.indexOf("[첨부 시각 자료]");
    if (markerIndex < 0) return { request: text.trim(), names: [] };
    const block = text.slice(markerIndex);
    const names = Array.from(block.matchAll(/^-\s+([^:\n]+):\s+.+$/gm))
      .map((match) => match[1].trim())
      .filter(Boolean);
    return {
      request: text.slice(0, markerIndex).trim(),
      names: Array.from(new Set(names)),
    };
  }

  function visibleCurrentResult() {
    if (elements.completed.hidden) return "";
    const result = String(elements.resultContent?.innerText || "").trim();
    const candidateState = String(
      document.querySelector("#next-loop-panel")?.innerText || "",
    ).trim();
    const combined = [result, candidateState].filter(Boolean).join("\n\n");
    return combined.slice(0, 18000);
  }

  function attachmentInstruction(names) {
    if (!names.length) return "";
    return `\n\n[이미지 첨부 안내]\nPSOS에 첨부했던 이미지: ${names.join(", ")}\n일반 ChatGPT는 PSOS의 로컬 파일 경로를 열 수 없다. 사용자가 이 지시문과 함께 같은 이미지를 ChatGPT 대화에 직접 첨부한 경우에만 이미지를 근거로 사용한다. 이미지가 보이지 않으면 첨부를 요청하거나 다른 근거로 가능한 결론을 내린다.`;
  }

  function buildInitialPacket(route, request, previous = "", attachmentNames = []) {
    const priorBlock = previous
      ? `\n\n[현재 PSOS 결과]\n${previous}\n\n위 결과를 단순 평가하지 말고, 쓸 만한 근거는 보존하면서 사용자의 원래 요청을 끝까지 해결한 새 최종 결과로 완성한다.`
      : "";
    return `당신은 Personal Problem-Solving OS의 수동 실행 엔진이다.

${routeInstructions(route)}

[공통 원칙]
1. 사용자의 질문을 다른 문제로 바꾸지 않는다.
2. 사용자 정의, 대상 범위, 시간 순서와 고정 조건을 보존한다.
3. 그럴듯한 일반론보다 실제 판단과 행동 결론을 우선한다.
4. 검증하지 않은 사실을 확신하지 않는다.
5. 내부 추론 과정이나 PSOS 작동 설명은 출력하지 않는다.
6. 답변 맨 앞에 결론을 두고, 그 뒤에 핵심 근거와 위험을 붙인다.

[사용자 요청]
${request}${attachmentInstruction(attachmentNames)}${priorBlock}`;
  }

  function buildContinuationPacket(route, request, previous, correction) {
    return `당신은 Personal Problem-Solving OS의 수동 후속 실행 엔진이다.

${routeInstructions(route)}

이전 답변을 처음부터 버리지 말고, 맞는 사실과 근거는 보존하면서 사용자의 교정이 필요한 부분만 다시 조사하거나 수정한다.

[원래 요청]
${request}

[이전 답변]
${previous}

[사용자 교정]
${correction}

[출력]
교정이 반영된 완성된 새 답변만 제시한다. 변경 내역 설명이나 메타 설명은 붙이지 않는다.`;
  }

  const toggle = document.createElement("label");
  toggle.className = "workflow-manual-toggle manual-v3-toggle";
  toggle.innerHTML = `
    <input id="chatgpt-manual-enabled" type="checkbox">
    <span>
      <strong>Codex 없이 계속</strong>
      <small>한 번 복사하고, 답변을 붙여 넣으면 끝납니다.</small>
    </span>
  `;
  guideActions.insertBefore(toggle, guideActions.lastElementChild);
  const toggleInput = toggle.querySelector("#chatgpt-manual-enabled");

  const panel = document.createElement("section");
  panel.id = "chatgpt-manual-panel";
  panel.className = "chatgpt-manual-panel manual-v3-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="chatgpt-manual-heading">
      <div>
        <span class="workflow-kicker">Codex 없는 간편 실행</span>
        <h3>ChatGPT에 보내고, 답변만 다시 붙여 넣으세요.</h3>
        <p id="chatgpt-manual-summary">요청을 입력하면 자동으로 작업 지시문을 만듭니다.</p>
      </div>
      <span id="chatgpt-manual-route" class="workflow-badge"></span>
    </div>

    <ol class="manual-v3-progress" aria-label="수동 실행 단계">
      <li data-step="1"><strong>1</strong><span>ChatGPT 열기</span></li>
      <li data-step="2"><strong>2</strong><span>답변 붙이기</span></li>
      <li data-step="3"><strong>3</strong><span>끝내기</span></li>
    </ol>

    <section class="manual-v3-step" data-manual-step="1">
      <div class="manual-v3-step-head">
        <div><strong>1. ChatGPT에서 실행</strong><p>작업 종류에 맞는 지시문을 자동으로 복사합니다.</p></div>
        <button id="chatgpt-manual-open" type="button">복사하고 ChatGPT 열기</button>
      </div>
      <p id="chatgpt-manual-attachment-note" class="manual-v3-attachment-note" hidden></p>
      <details class="manual-v3-packet-details">
        <summary>보낼 내용 확인·직접 복사</summary>
        <textarea id="chatgpt-manual-packet" rows="12" readonly></textarea>
        <button id="chatgpt-manual-copy" type="button" class="secondary-button">내용만 복사</button>
      </details>
    </section>

    <section class="manual-v3-step" data-manual-step="2">
      <label class="field-label" for="chatgpt-manual-response">
        <span>2. ChatGPT 답변 붙여넣기</span>
        <textarea id="chatgpt-manual-response" rows="11" placeholder="ChatGPT 답변 전체를 여기에 붙여 넣으세요."></textarea>
      </label>
      <div class="manual-v3-finish-actions">
        <button id="chatgpt-manual-fix" type="button" class="secondary-button">한 번 더 고치기</button>
        <button id="chatgpt-manual-save" type="button">이 답변으로 끝내기</button>
      </div>
    </section>

    <section id="chatgpt-manual-followup" class="manual-v3-step manual-v3-followup" data-manual-step="3" hidden>
      <label class="field-label" for="chatgpt-manual-correction">
        <span>바꿀 점 한 줄</span>
        <textarea id="chatgpt-manual-correction" rows="3" placeholder="예: 결론을 먼저 말하고, 후보 2는 제외해. 차트 위험을 더 크게 반영해."></textarea>
      </label>
      <button id="chatgpt-manual-followup-copy" type="button">후속 지시문 복사</button>
      <p>복사한 내용을 방금 사용한 같은 ChatGPT 대화에 붙여 넣고, 새 답변을 위 칸에 덮어쓰면 됩니다.</p>
    </section>

    <div class="manual-v3-footer">
      <span id="chatgpt-manual-status" role="status" aria-live="polite"></span>
      <button id="chatgpt-manual-reset" type="button" class="secondary-button">처음부터</button>
    </div>
  `;
  guide.insertAdjacentElement("afterend", panel);

  const packet = panel.querySelector("#chatgpt-manual-packet");
  const response = panel.querySelector("#chatgpt-manual-response");
  const correction = panel.querySelector("#chatgpt-manual-correction");
  const followup = panel.querySelector("#chatgpt-manual-followup");
  const routeBadge = panel.querySelector("#chatgpt-manual-route");
  const summary = panel.querySelector("#chatgpt-manual-summary");
  const status = panel.querySelector("#chatgpt-manual-status");
  const attachmentNote = panel.querySelector("#chatgpt-manual-attachment-note");
  const progressItems = panel.querySelectorAll(".manual-v3-progress li");

  function persist() {
    const snapshot = {
      enabled: state.enabled,
      route: state.route,
      request: state.request,
      packet: packet.value,
      response: response.value,
      correction: correction.value,
      includeCurrentResult: state.includeCurrentResult,
      attachmentNames: state.attachmentNames,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  }

  function restore() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved || typeof saved !== "object") return;
      state.enabled = Boolean(saved.enabled);
      state.route = typeof saved.route === "string" ? saved.route : "direct";
      state.request = typeof saved.request === "string" ? saved.request : "";
      state.packet = typeof saved.packet === "string" ? saved.packet : "";
      state.response = typeof saved.response === "string" ? saved.response : "";
      state.correction = typeof saved.correction === "string" ? saved.correction : "";
      state.includeCurrentResult = Boolean(saved.includeCurrentResult);
      state.attachmentNames = Array.isArray(saved.attachmentNames) ? saved.attachmentNames : [];
      packet.value = state.packet;
      response.value = state.response;
      correction.value = state.correction;
    } catch (_error) {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }

  function updateProgress() {
    let active = 1;
    if (response.value.trim()) active = 3;
    else if (state.packet) active = 2;
    progressItems.forEach((item) => {
      const step = Number(item.dataset.step);
      item.classList.toggle("is-active", step === active);
      item.classList.toggle("is-done", step < active);
    });
  }

  function updateHeader() {
    routeBadge.textContent = routeLabels[state.route] || state.route;
    routeBadge.dataset.route = state.route;
    summary.textContent = state.includeCurrentResult
      ? "현재 결과를 보존하면서 일반 ChatGPT에서 결론까지 이어갑니다."
      : `${routeLabels[state.route] || state.route} 작업을 일반 ChatGPT에서 끝까지 수행합니다.`;
    attachmentNote.hidden = !state.attachmentNames.length;
    attachmentNote.textContent = state.attachmentNames.length
      ? `PSOS에 넣었던 이미지 ${state.attachmentNames.length}장도 열린 ChatGPT 창에 직접 끌어다 놓아야 합니다: ${state.attachmentNames.join(", ")}`
      : "";
  }

  function refreshPacket(form = elements.form, includeCurrentResult = false) {
    const rawRequest = currentRequest(form) || state.request;
    const parsed = stripAttachmentBlock(rawRequest);
    state.request = parsed.request;
    state.attachmentNames = parsed.names;
    state.route = classify(state.request, form);
    state.includeCurrentResult = Boolean(includeCurrentResult);
    const previous = state.includeCurrentResult ? visibleCurrentResult() : "";
    state.packet = state.request
      ? buildInitialPacket(state.route, state.request, previous, state.attachmentNames)
      : "";
    packet.value = state.packet;
    updateHeader();
    updateProgress();
    persist();
  }

  function setEnabled(enabled, message = "") {
    state.enabled = Boolean(enabled);
    toggleInput.checked = state.enabled;
    panel.hidden = !state.enabled;
    document.body.classList.toggle("chatgpt-manual-enabled", state.enabled);
    if (state.enabled) {
      refreshPacket();
      if (message) status.textContent = message;
    }
    persist();
  }

  async function copyText(text) {
    await navigator.clipboard.writeText(text);
  }

  async function copyAndOpen() {
    if (!packet.value.trim()) {
      status.textContent = "먼저 요청을 입력해 주세요.";
      elements.request.focus();
      return;
    }
    const opened = window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
    try {
      await copyText(packet.value);
      status.textContent = state.attachmentNames.length
        ? "지시문을 복사했습니다. 열린 ChatGPT에 이미지도 직접 첨부해 주세요."
        : "지시문을 복사했습니다. 열린 ChatGPT에 붙여 넣으세요.";
      if (!opened) status.textContent += " 팝업이 차단되었다면 ChatGPT를 직접 열어 주세요.";
      updateProgress();
    } catch (_error) {
      panel.querySelector(".manual-v3-packet-details").open = true;
      packet.focus();
      packet.select();
      status.textContent = "자동 복사에 실패했습니다. 선택된 내용을 직접 복사해 주세요.";
    }
  }

  function saveManualResult() {
    const text = response.value.trim();
    if (!text) {
      response.focus();
      status.textContent = "먼저 ChatGPT 답변을 붙여 넣어 주세요.";
      return;
    }
    state.response = text;
    persist();
    showCompleted({
      run_id: `manual-chatgpt-${Date.now()}`,
      route: `MANUAL CHATGPT · ${routeLabels[state.route] || state.route}`,
      execution_status: "completed",
      result_markdown: text,
      artifacts: [],
      evidence: [],
      limitations: ["일반 ChatGPT에서 수동 실행한 답변을 PSOS에 저장했습니다."],
      workspace_receipt: null,
      workspace_rollback: null,
    });
    status.textContent = "이 답변을 PSOS 결과로 저장했습니다.";
    updateProgress();
  }

  function revealFollowup() {
    if (!response.value.trim()) {
      response.focus();
      status.textContent = "먼저 ChatGPT 답변을 붙여 넣어 주세요.";
      return;
    }
    followup.hidden = false;
    correction.focus();
    followup.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function copyFollowup() {
    const previous = response.value.trim();
    const change = correction.value.trim();
    if (!previous) {
      response.focus();
      return;
    }
    if (!change) {
      correction.focus();
      status.textContent = "바꿀 점을 한 줄로 적어 주세요.";
      return;
    }
    const followupPacket = buildContinuationPacket(
      state.route,
      state.request,
      previous,
      change,
    );
    try {
      await copyText(followupPacket);
      status.textContent = "후속 지시문을 복사했습니다. 같은 ChatGPT 대화에 붙여 넣으세요.";
      state.correction = change;
      persist();
    } catch (_error) {
      packet.value = followupPacket;
      panel.querySelector(".manual-v3-packet-details").open = true;
      packet.focus();
      packet.select();
      status.textContent = "자동 복사에 실패해 아래에 내용을 열었습니다.";
    }
  }

  function resetManual() {
    state.request = "";
    state.packet = "";
    state.response = "";
    state.correction = "";
    state.includeCurrentResult = false;
    state.attachmentNames = [];
    packet.value = "";
    response.value = "";
    correction.value = "";
    followup.hidden = true;
    status.textContent = "";
    window.localStorage.removeItem(STORAGE_KEY);
    refreshPacket();
    response.focus();
  }

  document.addEventListener(
    "submit",
    (event) => {
      if (!state.enabled) return;
      if (event.target !== elements.form && event.target !== promptUi.form) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      refreshPacket(event.target, false);
      panel.hidden = false;
      copyAndOpen();
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    true,
  );

  toggleInput.addEventListener("change", () => setEnabled(toggleInput.checked));
  elements.request.addEventListener("input", () => {
    if (state.enabled && !state.includeCurrentResult) refreshPacket(elements.form, false);
  });
  promptUi.request.addEventListener("input", () => {
    if (state.enabled) refreshPacket(promptUi.form, false);
  });
  response.addEventListener("input", () => {
    state.response = response.value;
    updateProgress();
    persist();
  });
  correction.addEventListener("input", () => {
    state.correction = correction.value;
    persist();
  });
  panel.querySelector("#chatgpt-manual-open").addEventListener("click", copyAndOpen);
  panel.querySelector("#chatgpt-manual-copy").addEventListener("click", async () => {
    try {
      await copyText(packet.value);
      status.textContent = "보낼 내용을 복사했습니다.";
    } catch (_error) {
      packet.focus();
      packet.select();
      status.textContent = "선택된 내용을 직접 복사해 주세요.";
    }
  });
  panel.querySelector("#chatgpt-manual-save").addEventListener("click", saveManualResult);
  panel.querySelector("#chatgpt-manual-fix").addEventListener("click", revealFollowup);
  panel.querySelector("#chatgpt-manual-followup-copy").addEventListener("click", copyFollowup);
  panel.querySelector("#chatgpt-manual-reset").addEventListener("click", resetManual);

  const continueButton = document.createElement("button");
  continueButton.id = "chatgpt-manual-continue-current";
  continueButton.type = "button";
  continueButton.className = "secondary-button manual-v3-continue";
  continueButton.textContent = "이 결과를 ChatGPT에서 계속";
  continueButton.hidden = true;
  elements.evidencePanel.insertAdjacentElement("beforebegin", continueButton);
  continueButton.addEventListener("click", () => {
    setEnabled(true);
    refreshPacket(elements.form, true);
    copyAndOpen();
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function syncContinueButton() {
    continueButton.hidden = elements.completed.hidden || !visibleCurrentResult();
  }

  const fallbackButton = document.createElement("button");
  fallbackButton.type = "button";
  fallbackButton.className = "secondary-button chatgpt-error-fallback";
  fallbackButton.textContent = "Codex 없이 바로 계속";
  fallbackButton.hidden = true;
  errorPanel.appendChild(fallbackButton);
  fallbackButton.addEventListener("click", () => {
    setEnabled(true, "Codex 대신 일반 ChatGPT에서 같은 요청을 이어갑니다.");
    refreshPacket(elements.form, false);
    copyAndOpen();
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function updateErrorFallback() {
    const message = String(elements.errorMessage.textContent || "");
    const unavailable = /(codex|usage|quota|credit|capacity|rate.?limit|한도|용량|사용량|크레딧|할당량)/i.test(message);
    const shouldHide = elements.error.hidden || !unavailable;
    if (fallbackButton.hidden !== shouldHide) fallbackButton.hidden = shouldHide;
  }

  new MutationObserver(updateErrorFallback).observe(errorPanel, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  new MutationObserver(updateErrorFallback).observe(elements.errorMessage, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  new MutationObserver(syncContinueButton).observe(elements.completed, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  new MutationObserver(syncContinueButton).observe(elements.resultContent, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  restore();
  toggleInput.checked = state.enabled;
  panel.hidden = !state.enabled;
  document.body.classList.toggle("chatgpt-manual-enabled", state.enabled);
  if (state.enabled) {
    updateHeader();
    updateProgress();
  }
  updateErrorFallback();
  syncContinueButton();

  window.PSOSManualChatGPT = Object.freeze({
    version: 3,
    classify,
    buildInitialPacket,
    buildContinuationPacket,
    enable: () => setEnabled(true),
  });
})();
