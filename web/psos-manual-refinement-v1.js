(() => {
  const panel = document.querySelector("#manual-controller-panel");
  const controller = window.PSOSManualController;
  const terminal = panel?.querySelector("#manual-controller-terminal");
  if (!panel || !controller || !terminal || typeof requestJson !== "function") return;

  const legacyContinue = document.querySelector("#manual-v5-continue-current");
  if (legacyContinue) {
    legacyContinue.textContent = "이 결과에 수정 의견 반영하기";
    legacyContinue.title = "현재 결과를 기준으로 이유와 수정 방향을 입력해 이어갑니다.";
  }

  const section = document.createElement("section");
  section.id = "manual-controller-refinement";
  section.className = "manual-controller-card manual-controller-refinement";
  section.hidden = true;
  section.innerHTML = `
    <div class="manual-controller-refinement-head">
      <div>
        <strong>이 결과를 바탕으로 다시 다듬기</strong>
        <p>새 요청으로 버리지 않습니다. 기존 결과와 근거를 남긴 채, 사용자가 말한 이유와 방향을 다음 행동의 명시 조건으로 씁니다.</p>
      </div>
      <button id="manual-controller-refinement-open" type="button">결과에 의견 반영하기</button>
    </div>

    <div id="manual-controller-refinement-form" class="manual-controller-refinement-form" hidden>
      <label class="field-label" for="manual-controller-refinement-reason">
        <span>왜 바꾸려는지</span>
        <textarea id="manual-controller-refinement-reason" rows="4" maxlength="8000" placeholder="예: 답변 자체는 괜찮지만, 좋은 기업과 오늘 사기 좋은 가격을 구분하지 않았다."></textarea>
      </label>
      <label class="field-label" for="manual-controller-refinement-direction">
        <span>다음에는 어떤 방향으로 갈지</span>
        <textarea id="manual-controller-refinement-direction" rows="5" maxlength="8000" placeholder="예: 시장 후보를 넓게 다시 보고, 오늘 진입 손익비 기준으로 최종 1순위를 골라라."></textarea>
      </label>
      <div class="manual-controller-refinement-actions">
        <span id="manual-controller-refinement-status" role="status" aria-live="polite"></span>
        <div>
          <button id="manual-controller-refinement-cancel" type="button" class="secondary-button">취소</button>
          <button id="manual-controller-refinement-submit" type="button">이 의견으로 다음 행동 만들기</button>
        </div>
      </div>
    </div>

    <p id="manual-controller-refinement-limit" class="manual-controller-refinement-limit" hidden></p>
  `;
  terminal.insertAdjacentElement("afterend", section);

  const openButton = section.querySelector("#manual-controller-refinement-open");
  const form = section.querySelector("#manual-controller-refinement-form");
  const reasonField = section.querySelector("#manual-controller-refinement-reason");
  const directionField = section.querySelector("#manual-controller-refinement-direction");
  const cancelButton = section.querySelector("#manual-controller-refinement-cancel");
  const submitButton = section.querySelector("#manual-controller-refinement-submit");
  const statusNode = section.querySelector("#manual-controller-refinement-status");
  const limitNode = section.querySelector("#manual-controller-refinement-limit");
  let busy = false;
  let formOpened = false;
  let rendering = false;

  function setHidden(node, hidden) {
    const next = Boolean(hidden);
    if (node.hidden !== next) node.hidden = next;
  }

  function setText(node, text) {
    const next = String(text || "");
    if (node.textContent !== next) node.textContent = next;
  }

  function isTerminal(status) {
    return ["completed", "partial", "blocked"].includes(status);
  }

  function render() {
    if (rendering) return;
    rendering = true;
    try {
      const session = controller.getSession();
      const terminalSession = Boolean(session && isTerminal(session.status));
      setHidden(section, !terminalSession);
      if (!terminalSession) {
        setHidden(form, true);
        formOpened = false;
        return;
      }

      const exhausted = session.budget.used_actions >= session.budget.max_actions;
      setHidden(openButton, exhausted || formOpened);
      setHidden(form, exhausted || !formOpened);
      setHidden(limitNode, !exhausted);
      setText(
        limitNode,
        exhausted
          ? "이 세션은 허용된 AI 행동을 모두 사용했습니다. 이 경우에는 ‘요청 바꾸기’로 새 세션을 시작해야 합니다."
          : "",
      );
    } finally {
      rendering = false;
    }
  }

  function openForm() {
    formOpened = true;
    setText(statusNode, "");
    render();
    reasonField.focus();
    section.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function closeForm() {
    formOpened = false;
    setText(statusNode, "");
    render();
  }

  async function submitRefinement() {
    const session = controller.getSession();
    const reason = reasonField.value.trim();
    const direction = directionField.value.trim();
    if (!session || !isTerminal(session.status)) {
      setText(statusNode, "수정할 완료 결과가 없습니다.");
      return;
    }
    if (!direction) {
      directionField.focus();
      setText(statusNode, "다음 방향을 적어 주세요.");
      return;
    }

    busy = true;
    submitButton.disabled = true;
    cancelButton.disabled = true;
    setText(statusNode, "기존 결과와 근거를 보존하고 다음 행동을 만들고 있습니다.");
    try {
      await requestJson(
        `/api/manual-controller/sessions/${encodeURIComponent(session.session_id)}/refine`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason, direction }),
        },
      );
      reasonField.value = "";
      directionField.value = "";
      formOpened = false;
      await controller.reload();
      setText(statusNode, "사용자 의견을 반영한 다음 행동을 만들었습니다.");
      panel.querySelector("#manual-controller-progress")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    } catch (error) {
      setText(statusNode, error.message);
    } finally {
      busy = false;
      submitButton.disabled = false;
      cancelButton.disabled = false;
      render();
    }
  }

  openButton.addEventListener("click", openForm);
  cancelButton.addEventListener("click", closeForm);
  submitButton.addEventListener("click", submitRefinement);

  new MutationObserver(() => {
    if (!busy) render();
  }).observe(panel, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["hidden", "class", "data-route"],
  });
  render();

  window.PSOSManualRefinement = Object.freeze({
    version: 1,
    open: openForm,
    render,
  });
})();
