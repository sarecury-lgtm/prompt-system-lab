(() => {
  const panel = document.querySelector("#manual-controller-panel");
  const controller = window.PSOSManualController;
  if (!panel || !controller) return;

  const header = panel.querySelector(".manual-controller-head");
  const statusBadge = panel.querySelector("#manual-controller-status-badge");
  const resetButton = panel.querySelector("#manual-controller-reset");
  const requestField = panel.querySelector("#manual-controller-request");
  if (!header || !statusBadge || !resetButton || !requestField) return;

  const headActions = document.createElement("div");
  headActions.className = "manual-controller-head-actions";
  const switchButton = document.createElement("button");
  switchButton.id = "manual-controller-switch-request";
  switchButton.type = "button";
  switchButton.className = "secondary-button";
  switchButton.textContent = "요청 바꾸기";
  headActions.append(statusBadge, switchButton);
  header.appendChild(headActions);

  const currentRequest = document.createElement("section");
  currentRequest.id = "manual-controller-current-request";
  currentRequest.className = "manual-controller-current-request";
  currentRequest.hidden = true;
  currentRequest.innerHTML = `
    <span>현재 요청</span>
    <strong id="manual-controller-current-request-text"></strong>
  `;
  header.insertAdjacentElement("afterend", currentRequest);
  const currentRequestText = currentRequest.querySelector(
    "#manual-controller-current-request-text",
  );

  let rendering = false;

  function render() {
    if (rendering) return;
    rendering = true;
    try {
      const session = controller.getSession();
      const hasSession = Boolean(session);
      switchButton.hidden = !hasSession;
      currentRequest.hidden = !hasSession;
      const nextText = hasSession ? String(session.request || "").trim() : "";
      if (currentRequestText.textContent !== nextText) {
        currentRequestText.textContent = nextText;
      }
    } finally {
      rendering = false;
    }
  }

  switchButton.addEventListener("click", () => {
    resetButton.click();
    render();
    requestField.focus();
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  new MutationObserver(render).observe(panel, {
    subtree: true,
    childList: true,
    attributes: true,
  });
  render();

  window.PSOSManualRequestSwitch = Object.freeze({
    version: 1,
    render,
  });
})();
