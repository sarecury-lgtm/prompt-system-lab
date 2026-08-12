(() => {
  if (!elements?.form || !elements?.completed || !elements?.runId) return;

  const requestActions = elements.form.querySelector(".request-actions");
  const searchControl = requestActions?.querySelector(".check-control");
  if (!requestActions || !searchControl) return;

  const control = document.createElement("label");
  control.className = "check-control next-loop-control";
  control.innerHTML = `
    <input id="next-loop-enabled" type="checkbox">
    <span>
      <strong>후보 교정 루프</strong>
      <small>먼저 후보를 모은 뒤 한 줄 교정으로 필요한 부분만 다시 조사합니다.</small>
    </span>
  `;
  requestActions.insertBefore(control, searchControl);
  const toggle = control.querySelector("#next-loop-enabled");

  function syncMode() {
    const enabled = toggle.checked;
    if (enabled) {
      elements.modes.forEach((mode) => {
        mode.checked = mode.value === "read";
        if (mode.value === "write") mode.disabled = true;
      });
      elements.search.checked = true;
      elements.safetyNote.textContent =
        "정보원을 정찰하고 후보 작업대에서 멈춥니다. 후보를 본 뒤 짧게 빼거나 조건을 바꿀 수 있습니다.";
    } else {
      elements.modes.forEach((mode) => {
        mode.disabled = false;
      });
      updateMode();
    }
  }
  toggle.addEventListener("change", syncMode);

  async function submitNextLoop(event) {
    if (!toggle.checked) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const request = elements.request.value.trim();
    if (!request) {
      elements.request.focus();
      return;
    }
    window.clearTimeout(pollTimer);
    elements.submit.disabled = true;
    setResultState("running");
    elements.runningTitle.textContent = "정보원을 정찰하고 있습니다.";
    elements.runningDetail.textContent =
      "답이 압축된 정보원을 찾고 첫 후보 작업대를 만듭니다.";
    try {
      const job = await requestJson("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          search_enabled: true,
          execution_mode: "next_loop",
        }),
      });
      activeJobId = job.job_id;
      window.sessionStorage.setItem(activeJobStorageKey, activeJobId);
      pollJob();
    } catch (error) {
      showError(error.message);
    }
  }
  elements.form.addEventListener("submit", submitNextLoop, true);

  const panel = document.createElement("section");
  panel.id = "next-loop-panel";
  panel.className = "next-loop-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="next-loop-heading">
      <div>
        <span class="next-loop-kicker">후보 작업대</span>
        <h3>한 줄만 고치면 필요한 부분만 다시 움직입니다.</h3>
        <p id="next-loop-summary"></p>
      </div>
      <span id="next-loop-state" class="next-loop-state"></span>
    </div>
    <div id="next-loop-candidates" class="next-loop-candidates"></div>
    <form id="next-loop-correction-form" class="next-loop-form" hidden>
      <label for="next-loop-correction">후보나 조건을 짧게 교정</label>
      <div class="next-loop-input-row">
        <textarea id="next-loop-correction" rows="2" maxlength="2000" placeholder="예: candidate-002 제외 / 전부 비쌈 / 100g당 1000원 이하 더 찾아"></textarea>
        <button type="submit">교정 반영</button>
      </div>
    </form>
    <form id="next-loop-answer-form" class="next-loop-form" hidden>
      <div id="next-loop-questions"></div>
      <button type="submit">답변하고 계속</button>
    </form>
    <p id="next-loop-message" class="next-loop-message" role="status" aria-live="polite"></p>
  `;
  elements.evidencePanel.insertAdjacentElement("afterend", panel);

  const stateNode = panel.querySelector("#next-loop-state");
  const summaryNode = panel.querySelector("#next-loop-summary");
  const candidatesNode = panel.querySelector("#next-loop-candidates");
  const correctionForm = panel.querySelector("#next-loop-correction-form");
  const correctionInput = panel.querySelector("#next-loop-correction");
  const answerForm = panel.querySelector("#next-loop-answer-form");
  const questionsNode = panel.querySelector("#next-loop-questions");
  const messageNode = panel.querySelector("#next-loop-message");

  let currentRunId = null;
  let loadingRunId = null;

  const stateLabels = {
    collecting: "수집 중",
    awaiting_correction: "교정 대기",
    awaiting_information: "답변 대기",
    running: "실행 중",
    researching: "부분 재조사",
    ready_for_verification: "검증 준비",
    completed: "완료",
    partial: "미완료",
  };
  const candidateLabels = {
    kept: "유지",
    excluded: "제외",
    needs_check: "확인 필요",
  };

  async function nRequestJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `요청 실패 (${response.status})`);
    return payload;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function renderCandidates(working) {
    clear(candidatesNode);
    const candidates = Array.isArray(working?.candidates) ? working.candidates : [];
    if (!candidates.length) {
      const empty = document.createElement("p");
      empty.textContent = "정찰에서 바로 쓸 수 있는 후보를 찾지 못했습니다.";
      candidatesNode.appendChild(empty);
      return;
    }
    const list = document.createElement("div");
    list.className = "next-loop-candidate-list";
    candidates.forEach((candidate) => {
      const item = document.createElement("article");
      item.className = `next-loop-candidate ${candidate.status || "needs_check"}`;
      const head = document.createElement("div");
      const name = document.createElement("a");
      name.href = candidate.source_url;
      name.target = "_blank";
      name.rel = "noopener noreferrer";
      name.textContent = candidate.name;
      const id = document.createElement("code");
      id.textContent = candidate.id;
      head.append(name, id);
      const meta = document.createElement("p");
      meta.textContent = `${candidate.source_family} · ${candidateLabels[candidate.status] || candidate.status}`;
      const reason = document.createElement("p");
      reason.textContent = candidate.exclusion_reason || candidate.why_actionable;
      item.append(head, meta, reason);
      list.appendChild(item);
    });
    candidatesNode.appendChild(list);
  }

  function renderQuestions(questions) {
    clear(questionsNode);
    (questions || []).forEach((question, index) => {
      const label = document.createElement("label");
      const text = document.createElement("span");
      text.textContent = question.text;
      const input = document.createElement("input");
      input.type = "text";
      input.name = question.id;
      input.required = true;
      input.maxLength = 1000;
      input.placeholder = Array.isArray(question.options)
        ? question.options.join(" / ")
        : "답변 입력";
      label.append(text, input);
      label.dataset.index = String(index + 1);
      questionsNode.appendChild(label);
    });
  }

  function renderState(payload) {
    const state = payload.interaction_state;
    const working = payload.candidate_working_set;
    const candidates = Array.isArray(working?.candidates) ? working.candidates : [];
    const kept = candidates.filter((item) => item.status !== "excluded").length;
    stateNode.textContent = stateLabels[state] || state || "상태 없음";
    summaryNode.textContent = candidates.length
      ? `남은 후보 ${kept}개 / 전체 ${candidates.length}개 · ${working?.source_plan?.strategy || "전략 없음"}`
      : "후보 없이 다음 행동을 결정합니다.";
    renderCandidates(working);
    correctionForm.hidden = state !== "awaiting_correction";
    answerForm.hidden = state !== "awaiting_information";
    if (state === "awaiting_information") {
      renderQuestions(payload.pending_questions || []);
    } else {
      clear(questionsNode);
    }
    panel.hidden = false;
  }

  async function loadState(runId, force = false) {
    if (!force && (runId === currentRunId || runId === loadingRunId)) return;
    loadingRunId = runId;
    messageNode.textContent = "후보 상태를 불러오고 있습니다.";
    try {
      const payload = await nRequestJson(
        `/api/next-loop/runs/${encodeURIComponent(runId)}`,
      );
      if (loadingRunId !== runId) return;
      currentRunId = runId;
      renderState(payload);
      messageNode.textContent = "";
    } catch (error) {
      if (loadingRunId !== runId) return;
      currentRunId = null;
      panel.hidden = true;
      if (!String(error.message).includes("찾을 수 없습니다")) {
        console.warn("next-loop state unavailable:", error);
      }
    } finally {
      if (loadingRunId === runId) loadingRunId = null;
    }
  }

  async function queueResume(body) {
    if (!currentRunId) return;
    messageNode.textContent = "교정을 해석하고 필요한 작업만 실행합니다.";
    correctionForm.querySelector("button").disabled = true;
    answerForm.querySelector("button").disabled = true;
    try {
      const payload = await nRequestJson(
        `/api/next-loop/runs/${encodeURIComponent(currentRunId)}/resume`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      currentRunId = null;
      activeJobId = payload.job.job_id;
      window.sessionStorage.setItem(activeJobStorageKey, activeJobId);
      setResultState("running");
      elements.runningTitle.textContent = "교정을 반영하고 있습니다.";
      elements.runningDetail.textContent =
        "기존 후보를 보존하고 재정렬·부분 재조사·검증 중 필요한 것만 수행합니다.";
      pollJob();
    } catch (error) {
      messageNode.textContent = error.message;
      correctionForm.querySelector("button").disabled = false;
      answerForm.querySelector("button").disabled = false;
    }
  }

  correctionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = correctionInput.value.trim();
    if (!text) {
      correctionInput.focus();
      return;
    }
    queueResume({ correction_text: text });
  });

  answerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const answers = {};
    new FormData(answerForm).forEach((value, key) => {
      const text = String(value).trim();
      if (text) answers[key] = text;
    });
    if (!Object.keys(answers).length) return;
    queueResume({ answers });
  });

  function syncRun(force = false) {
    const runId = elements.runId.textContent.trim();
    if (elements.completed.hidden || !runId) return;
    loadState(runId, force);
  }

  new MutationObserver(() => syncRun(true)).observe(elements.completed, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  new MutationObserver(() => syncRun(true)).observe(elements.runId, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  syncMode();
  syncRun();
})();
