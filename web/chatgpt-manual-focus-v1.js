(() => {
  const panel = document.querySelector("#chatgpt-manual-panel");
  const importedSection = document.querySelector("#manual-v5-imported");
  if (!panel || !importedSection) return;

  const engineSelector = document.querySelector(".engine-selector");
  const engineHeading = document.querySelector(".workspace > .section-heading");
  const resetButton = document.querySelector("#manual-v5-reset");
  const importedDetails = importedSection.querySelector("details");

  const completionNote = document.createElement("div");
  completionNote.id = "manual-v5-completion-note";
  completionNote.className = "manual-v5-focus-note";
  completionNote.hidden = true;
  completionNote.innerHTML = `
    <strong>수동 실행 완료</strong>
    <span>가져온 답변이 최종 결과입니다. 다른 실행 방식을 다시 고를 필요가 없습니다.</span>
  `;
  if (importedDetails) {
    importedSection.insertBefore(completionNote, importedDetails);
  } else {
    importedSection.appendChild(completionNote);
  }

  function setHidden(node, hidden) {
    if (!node) return;
    node.toggleAttribute("hidden", hidden);
    if (hidden) {
      node.setAttribute("aria-hidden", "true");
    } else {
      node.removeAttribute("aria-hidden");
    }
  }

  function syncManualFocus() {
    const enabled = document.body.classList.contains("manual-v5-enabled");
    const completed = enabled && !importedSection.hidden;

    setHidden(engineHeading, enabled);
    setHidden(engineSelector, enabled);
    completionNote.hidden = !completed;
    panel.classList.toggle("manual-v5-completed", completed);

    if (resetButton) {
      resetButton.textContent = completed ? "새 요청 시작" : "처음부터";
    }
  }

  new MutationObserver(syncManualFocus).observe(document.body, {
    attributes: true,
    attributeFilter: ["class"],
  });
  new MutationObserver(syncManualFocus).observe(importedSection, {
    attributes: true,
    attributeFilter: ["hidden"],
  });

  syncManualFocus();

  window.PSOSManualFocus = Object.freeze({
    version: 1,
    sync: syncManualFocus,
  });
})();
