(() => {
  if (
    typeof elements === "undefined" ||
    typeof requestJson !== "function" ||
    typeof showCompleted !== "function"
  ) return;

  const toggle = document.querySelector("#chatgpt-manual-enabled");
  const oldPanel = document.querySelector("#chatgpt-manual-panel");
  const guide = document.querySelector("#workflow-guide");
  if (!toggle || !oldPanel || !guide) return;

  const STORAGE_KEY = "psos-manual-controller-session-v1";
  let session = null;
  let busy = false;

  const panel = document.createElement("section");
  panel.id = "manual-controller-panel";
  panel.className = "manual-controller-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <header class="manual-controller-head">
      <div>
        <span class="workflow-kicker">같은 Controller · 수동 전송</span>
        <h3>Controller가 다음 행동을 고르고, ChatGPT에는 현재 행동 하나만 보냅니다.</h3>
        <p>Codex 자동 실행과 상태·완료 검사·반복 한도는 같고, AI 결과를 옮기는 과정만 수동입니다.</p>
      </div>
      <span id="manual-controller-status-badge" class="workflow-badge">준비</span>
    </header>

    <div class="manual-controller-isolation-note">
      <strong>채팅 공간</strong>
      <span>정확한 재현이 필요하면 임시 채팅을 쓰세요. 평소에는 프로젝트 채팅도 가능하지만, Controller는 아래 패킷에 명시된 상태만 필수 기준으로 사용합니다.</span>
    </div>

    <section id="manual-controller-start" class="manual-controller-card">
      <label class="field-label" for="manual-controller-request">
        <span>해결할 요청</span>
        <textarea id="manual-controller-request" rows="6" maxlength="10000" placeholder="평소처럼 요청을 적으세요."></textarea>
      </label>
      <details class="manual-controller-context-details">
        <summary>이번 작업에 명시적으로 넣을 문맥</summary>
        <textarea id="manual-controller-context" rows="5" maxlength="30000" placeholder="과거 대화나 프로젝트 기억 중 반드시 써야 할 내용만 넣습니다."></textarea>
      </details>
      <div class="manual-controller-actions">
        <button id="manual-controller-start-button" type="button">Controller 세션 시작</button>
      </div>
    </section>

    <section id="manual-controller-progress" class="manual-controller-card" hidden>
      <div class="manual-controller-progress-head">
        <div>
          <span id="manual-controller-route" class="workflow-badge"></span>
          <strong id="manual-controller-objective"></strong>
          <p id="manual-controller-reason"></p>
        </div>
        <div class="manual-controller-budget">
          <span id="manual-controller-action-budget"></span>
          <span id="manual-controller-change-budget"></span>
        </div>
      </div>
      <details class="manual-controller-packet-details">
        <summary>현재 Action Packet 확인</summary>
        <pre id="manual-controller-packet"></pre>
      </details>
      <div class="manual-controller-actions">
        <button id="manual-controller-copy" type="button">현재 행동 패킷 복사</button>
        <button id="manual-controller-open" type="button" class="secondary-button">ChatGPT 열기</button>
      </div>
    </section>

    <section id="manual-controller-result-input" class="manual-controller-card" hidden>
      <label class="field-label" for="manual-controller-answer">
        <span>ChatGPT 답변 전체 붙여넣기</span>
        <textarea id="manual-controller-answer" rows="13" placeholder="사용자용 답변과 마지막 Action Result까지 전부 붙여 넣으세요."></textarea>
      </label>
      <div class="manual-controller-actions">
        <button id="manual-controller-submit-result" type="button">결과를 Controller에 제출</button>
      </div>
    </section>

    <section id="manual-controller-user-input" class="manual-controller-card" hidden>
      <strong>Controller가 사용자 확인을 요청했습니다.</strong>
      <p id="manual-controller-question"></p>
      <textarea id="manual-controller-user-answer" rows="4" placeholder="질문에 답하세요."></textarea>
      <div class="manual-controller-actions">
        <button id="manual-controller-submit-user" type="button">답변 반영</button>
      </div>
    </section>

    <section id="manual-controller-terminal" class="manual-controller-card manual-controller-terminal" hidden>
      <strong id="manual-controller-terminal-title"></strong>
      <p id="manual-controller-terminal-detail"></p>
    </section>

    <details id="manual-controller-history-details" class="manual-controller-card" hidden>
      <summary>Controller 행동 기록</summary>
      <ol id="manual-controller-history"></ol>
    </details>

    <footer class="manual-controller-footer">
      <span id="manual-controller-message" role="status" aria-live="polite"></span>
      <button id="manual-controller-reset" type="button" class="secondary-button">새 요청 시작</button>
    </footer>
  `;
  oldPanel.insertAdjacentElement("afterend", panel);

  const requestField = panel.querySelector("#manual-controller-request");
  const contextField = panel.querySelector("#manual-controller-context");
  const startSection = panel.querySelector("#manual-controller-start");
  const progressSection = panel.querySelector("#manual-controller-progress");
  const resultInputSection = panel.querySelector("#manual-controller-result-input");
  const userInputSection = panel.querySelector("#manual-controller-user-input");
  const terminalSection = panel.querySelector("#manual-controller-terminal");
  const historyDetails = panel.querySelector("#manual-controller-history-details");
  const statusBadge = panel.querySelector("#manual-controller-status-badge");
  const routeBadge = panel.querySelector("#manual-controller-route");
  const objectiveNode = panel.querySelector("#manual-controller-objective");
  const reasonNode = panel.querySelector("#manual-controller-reason");
  const packetNode = panel.querySelector("#manual-controller-packet");
  const actionBudget = panel.querySelector("#manual-controller-action-budget");
  const changeBudget = panel.querySelector("#manual-controller-change-budget");
  const answerField = panel.querySelector("#manual-controller-answer");
  const questionNode = panel.querySelector("#manual-controller-question");
  const userAnswerField = panel.querySelector("#manual-controller-user-answer");
  const historyNode = panel.querySelector("#manual-controller-history");
  const messageNode = panel.querySelector("#manual-controller-message");
  const terminalTitle = panel.querySelector("#manual-controller-terminal-title");
  const terminalDetail = panel.querySelector("#manual-controller-terminal-detail");

  function setMessage(text) {
    messageNode.textContent = text || "";
  }

  function setBusy(value) {
    busy = Boolean(value);
    panel.querySelectorAll("button").forEach((button) => {
      if (button.id !== "manual-controller-reset") button.disabled = busy;
    });
  }

  function legacyCopy(text) {
    const node = document.createElement("textarea");
    node.value = text;
    node.setAttribute("readonly", "");
    node.style.position = "fixed";
    node.style.opacity = "0";
    document.body.appendChild(node);
    node.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } finally {
      node.remove();
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

  function statusCopy(value) {
    const map = {
      awaiting_execution: ["다음 행동", "Controller가 선택한 현재 행동을 ChatGPT에 보내세요."],
      awaiting_user_input: ["사용자 확인", "결론을 바꾸는 정보 하나를 확인해야 합니다."],
      completed: ["완료", "Controller의 완료 조건을 충족했습니다."],
      partial: ["부분 완료", "반복 한도 또는 검증 조건 때문에 정직한 부분 결과로 끝냈습니다."],
      blocked: ["차단", "현재 능력이나 자료로 핵심 행동을 수행할 수 없습니다."],
    };
    return map[value] || ["준비", "Controller 세션을 시작하세요."];
  }

  function renderHistory() {
    historyNode.replaceChildren();
    const actions = session?.actions || [];
    actions.forEach((action) => {
      const item = document.createElement("li");
      const result = action.result_status ? ` → ${action.result_status}` : "";
      item.textContent = `${action.action_number}. ${action.route} · ${action.objective}${result}`;
      historyNode.appendChild(item);
    });
    historyDetails.hidden = !actions.length;
  }

  function render() {
    const enabled = toggle.checked;
    panel.hidden = !enabled;
    document.body.classList.toggle("manual-controller-enabled", enabled);
    if (!enabled) return;

    if (!session) {
      statusBadge.textContent = "준비";
      statusBadge.dataset.route = "direct";
      startSection.hidden = false;
      progressSection.hidden = true;
      resultInputSection.hidden = true;
      userInputSection.hidden = true;
      terminalSection.hidden = true;
      historyDetails.hidden = true;
      requestField.readOnly = false;
      contextField.disabled = false;
      if (!requestField.value.trim() && elements.request?.value.trim()) {
        requestField.value = elements.request.value.trim();
      }
      return;
    }

    const [title, detail] = statusCopy(session.status);
    statusBadge.textContent = title;
    statusBadge.dataset.route = session.current_action?.packet?.route?.toLowerCase() || "direct";
    startSection.hidden = true;
    requestField.readOnly = true;
    contextField.disabled = true;
    actionBudget.textContent = `AI 행동 ${session.budget.used_actions}/${session.budget.max_actions}`;
    changeBudget.textContent = `방법 변경 ${session.budget.used_method_changes}/${session.budget.max_method_changes}`;

    const current = session.current_action;
    progressSection.hidden = session.status !== "awaiting_execution" || !current;
    resultInputSection.hidden = session.status !== "awaiting_execution" || !current;
    if (current) {
      routeBadge.textContent = current.packet.route;
      routeBadge.dataset.route = current.packet.route.toLowerCase();
      objectiveNode.textContent = current.packet.objective;
      reasonNode.textContent = current.packet.reason;
      packetNode.textContent = JSON.stringify(current.packet, null, 2);
    }

    userInputSection.hidden = session.status !== "awaiting_user_input";
    questionNode.textContent = session.awaiting_user_question || "";

    const terminal = ["completed", "partial", "blocked"].includes(session.status);
    terminalSection.hidden = !terminal;
    if (terminal) {
      terminalTitle.textContent = title;
      terminalDetail.textContent = detail;
      if (session.display_data) showCompleted(session.display_data);
    }
    renderHistory();
    window.localStorage.setItem(STORAGE_KEY, session.session_id);
  }

  async function startSession() {
    const request = requestField.value.trim() || elements.request?.value.trim() || "";
    if (!request) {
      requestField.focus();
      setMessage("먼저 요청을 입력해 주세요.");
      return;
    }
    setBusy(true);
    setMessage("Controller가 목표와 첫 행동을 고르고 있습니다.");
    try {
      session = await requestJson("/api/manual-controller/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          context: contextField.value.trim(),
        }),
      });
      elements.request.value = request;
      elements.request.dispatchEvent(new Event("input", { bubbles: true }));
      setMessage("첫 행동이 준비됐습니다.");
      render();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function loadSession(sessionId) {
    if (!sessionId) return;
    try {
      session = await requestJson(`/api/manual-controller/sessions/${encodeURIComponent(sessionId)}`);
      requestField.value = session.request || "";
      render();
    } catch (_error) {
      window.localStorage.removeItem(STORAGE_KEY);
      session = null;
      render();
    }
  }

  async function copyCurrentAction() {
    const prompt = session?.current_action?.execution_prompt || "";
    if (!prompt) {
      setMessage("복사할 현재 행동이 없습니다.");
      return;
    }
    const copied = await copyReliable(prompt);
    setMessage(
      copied
        ? "현재 행동 패킷을 복사했습니다. 같은 ChatGPT 대화에 붙여 넣으세요."
        : "자동 복사에 실패했습니다. Action Packet을 열어 직접 복사해 주세요.",
    );
  }

  function openChatGPT() {
    const opened = window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
    setMessage(opened ? "ChatGPT를 열었습니다." : "팝업이 차단됐습니다. ChatGPT를 직접 열어 주세요.");
  }

  async function submitResult() {
    const answer = answerField.value.trim();
    if (!session || !answer) {
      answerField.focus();
      setMessage("ChatGPT 답변 전체를 붙여 넣어 주세요.");
      return;
    }
    setBusy(true);
    setMessage("Controller가 완료 조건과 다음 행동을 판단하고 있습니다.");
    try {
      session = await requestJson(
        `/api/manual-controller/sessions/${encodeURIComponent(session.session_id)}/result`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer }),
        },
      );
      answerField.value = "";
      setMessage(
        session.status === "awaiting_execution"
          ? "아직 완료 조건이 남아 다음 행동을 새로 만들었습니다."
          : session.status === "awaiting_user_input"
            ? "사용자 확인이 필요한 질문 하나를 만들었습니다."
            : "Controller가 이 세션을 종료했습니다.",
      );
      render();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitUserInput() {
    const answer = userAnswerField.value.trim();
    if (!session || !answer) {
      userAnswerField.focus();
      setMessage("질문에 대한 답을 입력해 주세요.");
      return;
    }
    setBusy(true);
    try {
      session = await requestJson(
        `/api/manual-controller/sessions/${encodeURIComponent(session.session_id)}/input`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer }),
        },
      );
      userAnswerField.value = "";
      setMessage("사용자 답변을 고정 조건에 넣고 다음 행동을 만들었습니다.");
      render();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  function resetSession() {
    session = null;
    answerField.value = "";
    userAnswerField.value = "";
    contextField.value = "";
    requestField.value = "";
    window.localStorage.removeItem(STORAGE_KEY);
    setMessage("");
    render();
    requestField.focus();
  }

  toggle.addEventListener("change", () => {
    render();
    if (toggle.checked && !session) {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) loadSession(saved);
    }
  });
  requestField.addEventListener("input", () => {
    if (!session && elements.request.value !== requestField.value) {
      elements.request.value = requestField.value;
      elements.request.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  panel.querySelector("#manual-controller-start-button").addEventListener("click", startSession);
  panel.querySelector("#manual-controller-copy").addEventListener("click", copyCurrentAction);
  panel.querySelector("#manual-controller-open").addEventListener("click", openChatGPT);
  panel.querySelector("#manual-controller-submit-result").addEventListener("click", submitResult);
  panel.querySelector("#manual-controller-submit-user").addEventListener("click", submitUserInput);
  panel.querySelector("#manual-controller-reset").addEventListener("click", resetSession);

  const saved = window.localStorage.getItem(STORAGE_KEY);
  render();
  if (toggle.checked && saved) loadSession(saved);

  window.PSOSManualController = Object.freeze({
    version: 1,
    start: startSession,
    reload: () => loadSession(session?.session_id || saved),
    getSession: () => session,
  });
})();
