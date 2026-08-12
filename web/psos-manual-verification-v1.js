(() => {
  const panel = document.querySelector("#manual-controller-panel");
  const history = document.querySelector("#manual-controller-history-details");
  if (!panel || !window.PSOSManualController) return;

  const section = document.createElement("section");
  section.id = "manual-controller-verification";
  section.className = "manual-controller-card manual-controller-verification";
  section.hidden = true;
  section.innerHTML = `
    <div class="manual-controller-verification-head">
      <strong id="manual-controller-verification-title">Controller 검증</strong>
      <span id="manual-controller-verification-badge" class="workflow-badge"></span>
    </div>
    <p id="manual-controller-contract-summary"></p>
    <ul id="manual-controller-verification-missing"></ul>
    <div id="manual-controller-verification-next" class="manual-controller-verification-next" hidden>
      <span>다음 행동</span>
      <strong id="manual-controller-verification-next-text"></strong>
    </div>
  `;
  if (history) panel.insertBefore(section, history);
  else panel.appendChild(section);

  const title = section.querySelector("#manual-controller-verification-title");
  const badge = section.querySelector("#manual-controller-verification-badge");
  const summary = section.querySelector("#manual-controller-contract-summary");
  const missingList = section.querySelector("#manual-controller-verification-missing");
  const nextBox = section.querySelector("#manual-controller-verification-next");
  const nextText = section.querySelector("#manual-controller-verification-next-text");
  let lastSignature = "";

  function contractSummary(contract) {
    if (!contract) return "";
    const scope = contract.target_scope?.kind === "open_set" ? "열린 후보군" : "지정된 범위";
    const time = contract.decision_time || "unspecified";
    const count = contract.selection_count ? ` · 최종 ${contract.selection_count}개` : "";
    return `${contract.requested_action || "answer"} · ${time} · ${scope}${count}`;
  }

  function renderSignature(session) {
    return JSON.stringify({
      sessionId: session?.session_id || "",
      verification: session?.last_verification || null,
      contract: session?.request_contract || null,
      nextAction: session?.current_action?.packet
        ? {
            actionId: session.current_action.packet.action_id,
            route: session.current_action.packet.route,
            objective: session.current_action.packet.objective,
          }
        : null,
    });
  }

  function renderVerification() {
    const session = window.PSOSManualController.getSession();
    const signature = renderSignature(session);
    if (signature === lastSignature) return;
    lastSignature = signature;

    const verification = session?.last_verification;
    if (!session || !verification) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    const satisfied = Boolean(verification.satisfied);
    title.textContent = satisfied ? "Controller 검증 통과" : "Controller 검증 실패";
    badge.textContent = satisfied ? "충족" : `${verification.missing_conditions?.length || 0}개 누락`;
    badge.dataset.route = satisfied ? "direct" : "research";
    summary.textContent = contractSummary(session.request_contract);
    missingList.replaceChildren();
    (verification.missing_conditions || []).forEach((text) => {
      const item = document.createElement("li");
      item.textContent = text;
      missingList.appendChild(item);
    });
    missingList.hidden = satisfied || !missingList.children.length;

    const next = session.current_action?.packet;
    nextBox.hidden = !next || satisfied;
    nextText.textContent = next && !satisfied ? `${next.route} · ${next.objective}` : "";
  }

  new MutationObserver(renderVerification).observe(panel, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  renderVerification();

  window.PSOSManualVerification = Object.freeze({
    version: 1,
    render: renderVerification,
  });
})();
