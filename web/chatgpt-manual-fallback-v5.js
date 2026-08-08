(() => {
  if (
    typeof elements === "undefined" ||
    typeof promptUi === "undefined" ||
    typeof showCompleted !== "function" ||
    !window.PSOSManualProtocol
  ) return;

  const protocol = window.PSOSManualProtocol;
  const STORAGE_KEY = "psos-manual-job-workflow-v1";
  const guide = document.querySelector("#workflow-guide");
  const guideActions = guide?.querySelector(".workflow-guide-actions");
  if (!guide || !guideActions) return;

  const state = {
    enabled: false,
    packet: null,
    prompt: "",
    answer: "",
    imported: null,
    correction: "",
    copied: false,
    continuedFromResult: false,
  };

  function externalRouteHint(request) {
    const hint = window.PSOSWorkflowRouter?.classifyRequest(request) || "";
    const mapping = {
      direct: "DIRECT",
      research: "RESEARCH",
      candidate: "CANDIDATE",
      prompt: "PROMPT",
      write: "WRITE",
      decision: "DECISION",
    };
    return mapping[String(hint || "").toLowerCase()] || "";
  }

  function extractAttachments(request) {
    const text = String(request || "");
    const markerIndex = text.indexOf("[첨부 시각 자료]");
    if (markerIndex < 0) return { request: text.trim(), attachments: [] };
    const block = text.slice(markerIndex);
    const attachments = Array.from(block.matchAll(/^-\s+([^:\n]+):\s+.+$/gm))
      .map((match) => match[1].trim())
      .filter(Boolean);
    return {
      request: text.slice(0, markerIndex).trim(),
      attachments: Array.from(new Set(attachments)),
    };
  }

  function currentRenderedResult() {
    if (elements.completed.hidden) return "";
    return String(elements.resultContent?.innerText || "").trim().slice(0, 24000);
  }

  function currentOriginalRequest() {
    return String(elements.request?.value || "").trim();
  }

  const toggle = document.createElement("label");
  toggle.className = "workflow-manual-toggle manual-v5-toggle";
  toggle.innerHTML = `
    <input id="chatgpt-manual-enabled" type="checkbox">
    <span>
      <strong>ChatGPT 수동 실행</strong>
      <small>Job Packet을 한 번 보내고 결과를 붙여 넣습니다.</small>
    </span>
  `;
  guideActions.insertBefore(toggle, guideActions.lastElementChild);
  const toggleInput = toggle.querySelector("#chatgpt-manual-enabled");

  const panel = document.createElement("section");
  panel.id = "chatgpt-manual-panel";
  panel.className = "chatgpt-manual-panel manual-v5-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="manual-v5-heading">
      <div>
        <span class="workflow-kicker">Codex 없는 PSOS 실행</span>
        <h3>질문을 작업 패킷으로 보내고 결과를 다시 가져옵니다.</h3>
        <p>Goal Ledger, 조사·판단 절차와 완료 검증은 패킷 안에서 한 번에 실행됩니다.</p>
      </div>
      <span id="manual-v5-route" class="workflow-badge">DIRECT</span>
    </div>

    <label class="field-label manual-v5-request-label" for="manual-v5-request">
      <span>무엇을 해결할까요?</span>
      <textarea id="manual-v5-request" rows="6" maxlength="10000" placeholder="평소처럼 요청을 적으세요."></textarea>
    </label>

    <ol class="manual-v5-progress" aria-label="ChatGPT 수동 실행 단계">
      <li data-step="1"><strong>1</strong><span>패킷 복사</span></li>
      <li data-step="2"><strong>2</strong><span>답변 붙이기</span></li>
      <li data-step="3"><strong>3</strong><span>결과 또는 교정</span></li>
    </ol>

    <section class="manual-v5-step">
      <div class="manual-v5-step-head">
        <div>
          <strong>1. 실행 패킷 보내기</strong>
          <p>복사와 창 열기를 분리해 브라우저 권한 문제를 피합니다.</p>
        </div>
        <div class="manual-v5-actions">
          <button id="manual-v5-copy" type="button">실행 패킷 복사</button>
          <button id="manual-v5-open" type="button" class="secondary-button">ChatGPT 열기</button>
        </div>
      </div>
      <p id="manual-v5-attachment-note" class="manual-v5-note" hidden></p>
      <details id="manual-v5-packet-details" class="manual-v5-details">
        <summary>보낼 패킷 확인</summary>
        <textarea id="manual-v5-prompt" rows="16" readonly></textarea>
      </details>
    </section>

    <section class="manual-v5-step">
      <label class="field-label" for="manual-v5-answer">
        <span>2. ChatGPT 답변 전체 붙여넣기</span>
        <textarea id="manual-v5-answer" rows="13" placeholder="최종 답변과 마지막 Result Envelope까지 전부 붙여 넣으세요."></textarea>
      </label>
      <div class="manual-v5-step-head manual-v5-import-row">
        <p>Envelope가 빠져도 답변은 버리지 않고 일반 결과로 저장합니다.</p>
        <button id="manual-v5-import" type="button">결과 가져오기</button>
      </div>
    </section>

    <section id="manual-v5-imported" class="manual-v5-step manual-v5-imported" hidden>
      <div class="manual-v5-step-head">
        <div>
          <strong>3. 가져온 결과</strong>
          <p id="manual-v5-import-summary"></p>
        </div>
        <button id="manual-v5-fix" type="button" class="secondary-button">한 번 더 고치기</button>
      </div>
      <details class="manual-v5-details">
        <summary>가져온 상태와 진단 보기</summary>
        <pre id="manual-v5-envelope"></pre>
        <ul id="manual-v5-warnings"></ul>
      </details>
    </section>

    <section id="manual-v5-followup" class="manual-v5-step" hidden>
      <label class="field-label" for="manual-v5-correction">
        <span>바꿀 점</span>
        <textarea id="manual-v5-correction" rows="4" placeholder="예: 실적 전 소액 진입 가능성도 비교하고, 이미 제외한 후보는 다시 넣지 마."></textarea>
      </label>
      <div class="manual-v5-step-head manual-v5-import-row">
        <p>후속 패킷은 방금 사용한 같은 ChatGPT 대화에 붙여 넣습니다.</p>
        <button id="manual-v5-followup-copy" type="button">후속 패킷 복사</button>
      </div>
    </section>

    <div class="manual-v5-footer">
      <span id="manual-v5-status" role="status" aria-live="polite"></span>
      <button id="manual-v5-reset" type="button" class="secondary-button">처음부터</button>
    </div>
  `;
  guide.insertAdjacentElement("afterend", panel);

  const requestField = panel.querySelector("#manual-v5-request");
  const routeBadge = panel.querySelector("#manual-v5-route");
  const copyButton = panel.querySelector("#manual-v5-copy");
  const openButton = panel.querySelector("#manual-v5-open");
  const promptField = panel.querySelector("#manual-v5-prompt");
  const packetDetails = panel.querySelector("#manual-v5-packet-details");
  const answerField = panel.querySelector("#manual-v5-answer");
  const importButton = panel.querySelector("#manual-v5-import");
  const importedSection = panel.querySelector("#manual-v5-imported");
  const importSummary = panel.querySelector("#manual-v5-import-summary");
  const envelopeNode = panel.querySelector("#manual-v5-envelope");
  const warningList = panel.querySelector("#manual-v5-warnings");
  const fixButton = panel.querySelector("#manual-v5-fix");
  const followupSection = panel.querySelector("#manual-v5-followup");
  const correctionField = panel.querySelector("#manual-v5-correction");
  const followupCopyButton = panel.querySelector("#manual-v5-followup-copy");
  const attachmentNote = panel.querySelector("#manual-v5-attachment-note");
  const status = panel.querySelector("#manual-v5-status");
  const progressItems = panel.querySelectorAll(".manual-v5-progress li");

  function saveState() {
    const serializable = {
      enabled: state.enabled,
      packet: state.packet,
      prompt: promptField.value,
      answer: answerField.value,
      imported: state.imported,
      correction: correctionField.value,
      copied: state.copied,
      continuedFromResult: state.continuedFromResult,
      request: requestField.value,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(serializable));
  }

  function restoreState() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved || typeof saved !== "object") return;
      state.enabled = Boolean(saved.enabled);
      state.packet = saved.packet && typeof saved.packet === "object" ? saved.packet : null;
      state.prompt = typeof saved.prompt === "string" ? saved.prompt : "";
      state.answer = typeof saved.answer === "string" ? saved.answer : "";
      state.imported = saved.imported && typeof saved.imported === "object" ? saved.imported : null;
      state.correction = typeof saved.correction === "string" ? saved.correction : "";
      state.copied = Boolean(saved.copied);
      state.continuedFromResult = Boolean(saved.continuedFromResult);
      requestField.value = typeof saved.request === "string" ? saved.request : "";
      promptField.value = state.prompt;
      answerField.value = state.answer;
      correctionField.value = state.correction;
    } catch (_error) {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }

  function setProgress(step) {
    progressItems.forEach((item) => {
      const value = Number(item.dataset.step);
      item.classList.toggle("is-active", value === step);
      item.classList.toggle("is-done", value < step);
    });
  }

  function renderWarnings(warnings) {
    warningList.replaceChildren();
    (warnings || []).forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      warningList.appendChild(item);
    });
    warningList.hidden = !warningList.children.length;
  }

  function renderImported() {
    if (!state.imported) {
      importedSection.hidden = true;
      return;
    }
    importedSection.hidden = false;
    const envelope = state.imported.envelope;
    importSummary.textContent = envelope
      ? `${envelope.status || "partial"} · ${envelope.route || state.packet?.route_hint || "경로 없음"} · 상태까지 정상적으로 가져왔습니다.`
      : "답변은 가져왔지만 구조화된 상태는 없어 일반 결과로 저장했습니다.";
    envelopeNode.textContent = envelope ? JSON.stringify(envelope, null, 2) : "Result Envelope 없음";
    renderWarnings(state.imported.warnings || []);
  }

  function syncRoute() {
    const parsed = extractAttachments(requestField.value);
    const route = protocol.inferRoute(parsed.request, externalRouteHint(parsed.request));
    routeBadge.textContent = route;
    routeBadge.dataset.route = route.toLowerCase();
    attachmentNote.hidden = !parsed.attachments.length;
    attachmentNote.textContent = parsed.attachments.length
      ? `이 이미지도 열린 ChatGPT 대화에 직접 첨부해야 합니다: ${parsed.attachments.join(", ")}`
      : "";
    return { ...parsed, route };
  }

  function rebuildPacket({ keepJobId = true } = {}) {
    const parsed = syncRoute();
    if (!parsed.request) {
      state.packet = null;
      state.prompt = "";
      promptField.value = "";
      copyButton.disabled = true;
      return null;
    }
    const currentEnvelope = state.imported?.envelope || null;
    const packet = protocol.buildJobPacket({
      request: parsed.request,
      routeHint: parsed.route,
      previousAnswer: state.continuedFromResult ? currentRenderedResult() : "",
      previousEnvelope: state.continuedFromResult ? currentEnvelope : null,
      attachments: parsed.attachments,
      jobId: keepJobId ? state.packet?.job_id || "" : "",
    });
    state.packet = packet;
    state.prompt = protocol.buildExecutionPrompt(packet);
    promptField.value = state.prompt;
    copyButton.disabled = false;
    saveState();
    return packet;
  }

  function legacyCopy(text) {
    const temporary = document.createElement("textarea");
    temporary.value = text;
    temporary.setAttribute("readonly", "");
    temporary.style.position = "fixed";
    temporary.style.opacity = "0";
    document.body.appendChild(temporary);
    temporary.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } finally {
      temporary.remove();
    }
    return copied;
  }

  async function copyReliable(text) {
    const value = String(text || "").trim();
    if (!value) return false;
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_error) {
      return legacyCopy(value);
    }
  }

  async function copyInitialPacket() {
    const packet = rebuildPacket();
    if (!packet) {
      requestField.focus();
      status.textContent = "먼저 질문을 입력해 주세요.";
      return;
    }
    const copied = await copyReliable(promptField.value);
    if (!copied) {
      packetDetails.open = true;
      promptField.focus();
      promptField.select();
      status.textContent = "자동 복사에 실패했습니다. 선택된 내용을 Ctrl+C로 복사해 주세요.";
      return;
    }
    state.copied = true;
    setProgress(2);
    status.textContent = "실행 패킷을 복사했습니다. 이제 ChatGPT를 열어 붙여 넣으세요.";
    saveState();
  }

  function openChatGPT() {
    const opened = window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
    status.textContent = opened
      ? "ChatGPT를 열었습니다. 복사한 패킷을 붙여 넣으세요."
      : "팝업이 차단됐습니다. ChatGPT를 직접 열어 주세요.";
  }

  function importAnswer() {
    const raw = answerField.value.trim();
    if (!raw) {
      answerField.focus();
      status.textContent = "ChatGPT 답변 전체를 먼저 붙여 넣어 주세요.";
      return;
    }
    if (!state.packet) rebuildPacket();
    const imported = protocol.parseResultEnvelope(raw, state.packet?.job_id || "");
    state.answer = raw;
    state.imported = imported;
    state.continuedFromResult = false;
    renderImported();
    setProgress(3);
    saveState();
    showCompleted(protocol.toDisplayData({ packet: state.packet, imported }));
    status.textContent = imported.envelope
      ? "최종 답변과 PSOS 상태를 가져왔습니다."
      : "최종 답변을 가져왔습니다. Envelope가 없어 상태 저장은 제한됩니다.";
  }

  function revealFollowup() {
    if (!state.imported && !answerField.value.trim()) {
      answerField.focus();
      status.textContent = "먼저 결과를 가져와 주세요.";
      return;
    }
    followupSection.hidden = false;
    correctionField.focus();
    followupSection.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function copyFollowup() {
    const correction = correctionField.value.trim();
    const previousAnswer = state.imported?.answer || answerField.value.trim();
    if (!correction) {
      correctionField.focus();
      status.textContent = "바꿀 점을 입력해 주세요.";
      return;
    }
    if (!state.packet || !previousAnswer) {
      status.textContent = "이전 실행 패킷과 답변이 없습니다.";
      return;
    }
    const prompt = protocol.buildContinuationPrompt({
      packet: state.packet,
      previousAnswer,
      previousEnvelope: state.imported?.envelope || null,
      correction,
    });
    const copied = await copyReliable(prompt);
    if (!copied) {
      promptField.value = prompt;
      packetDetails.open = true;
      promptField.focus();
      promptField.select();
      status.textContent = "후속 패킷 복사에 실패했습니다. 선택된 내용을 Ctrl+C로 복사해 주세요.";
      return;
    }
    state.correction = correction;
    saveState();
    status.textContent = "후속 패킷을 복사했습니다. 방금 사용한 같은 ChatGPT 대화에 붙여 넣으세요.";
  }

  function setEnabled(enabled, { fromCurrentResult = false } = {}) {
    state.enabled = Boolean(enabled);
    toggleInput.checked = state.enabled;
    panel.hidden = !state.enabled;
    document.body.classList.toggle("manual-v5-enabled", state.enabled);
    if (state.enabled) {
      const sourceRequest = currentOriginalRequest();
      if (!requestField.value.trim() && sourceRequest) requestField.value = sourceRequest;
      state.continuedFromResult = Boolean(fromCurrentResult);
      rebuildPacket();
      renderImported();
      setProgress(state.imported ? 3 : state.copied ? 2 : 1);
      window.requestAnimationFrame(() => requestField.focus());
    }
    saveState();
  }

  function resetManual() {
    state.packet = null;
    state.prompt = "";
    state.answer = "";
    state.imported = null;
    state.correction = "";
    state.copied = false;
    state.continuedFromResult = false;
    requestField.value = "";
    promptField.value = "";
    answerField.value = "";
    correctionField.value = "";
    importedSection.hidden = true;
    followupSection.hidden = true;
    status.textContent = "";
    window.localStorage.removeItem(STORAGE_KEY);
    syncRoute();
    setProgress(1);
    requestField.focus();
  }

  toggleInput.addEventListener("change", () => setEnabled(toggleInput.checked));
  requestField.addEventListener("input", () => {
    state.copied = false;
    state.imported = null;
    state.continuedFromResult = false;
    importedSection.hidden = true;
    followupSection.hidden = true;
    if (elements.request.value !== requestField.value) {
      elements.request.value = requestField.value;
      elements.request.dispatchEvent(new Event("input", { bubbles: true }));
    }
    rebuildPacket({ keepJobId: false });
    setProgress(1);
  });
  answerField.addEventListener("input", saveState);
  correctionField.addEventListener("input", saveState);
  copyButton.addEventListener("click", copyInitialPacket);
  openButton.addEventListener("click", openChatGPT);
  importButton.addEventListener("click", importAnswer);
  fixButton.addEventListener("click", revealFollowup);
  followupCopyButton.addEventListener("click", copyFollowup);
  panel.querySelector("#manual-v5-reset").addEventListener("click", resetManual);

  const continueButton = document.createElement("button");
  continueButton.id = "manual-v5-continue-current";
  continueButton.type = "button";
  continueButton.className = "secondary-button manual-v5-continue";
  continueButton.textContent = "이 결과를 ChatGPT 수동 실행으로 계속";
  continueButton.hidden = true;
  elements.evidencePanel.insertAdjacentElement("beforebegin", continueButton);
  continueButton.addEventListener("click", () => {
    if (!requestField.value.trim()) requestField.value = currentOriginalRequest();
    setEnabled(true, { fromCurrentResult: true });
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function syncContinueButton() {
    continueButton.hidden = elements.completed.hidden || !currentRenderedResult();
  }

  new MutationObserver(syncContinueButton).observe(elements.completed, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  new MutationObserver(syncContinueButton).observe(elements.resultContent, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  restoreState();
  toggleInput.checked = state.enabled;
  panel.hidden = !state.enabled;
  document.body.classList.toggle("manual-v5-enabled", state.enabled);
  if (state.enabled) {
    rebuildPacket();
    renderImported();
    setProgress(state.imported ? 3 : state.copied ? 2 : 1);
  } else {
    syncRoute();
    setProgress(1);
  }
  syncContinueButton();

  window.PSOSManualChatGPT = Object.freeze({
    version: 5,
    enable: () => setEnabled(true),
    buildPacket: () => rebuildPacket(),
    importAnswer,
  });
})();
