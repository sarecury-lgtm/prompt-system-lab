(() => {
  const diagnosticMode = new URLSearchParams(window.location.search).get("diagnostic") === "1";

  function setHidden(node, hidden) {
    if (!node) return;
    node.toggleAttribute("hidden", hidden);
    if (hidden) {
      node.setAttribute("aria-hidden", "true");
    } else {
      node.removeAttribute("aria-hidden");
    }
  }

  function hideDefaultLegacyPaths() {
    document.body.classList.toggle("psos-diagnostic-mode", diagnosticMode);
    if (diagnosticMode) return;

    const integratedOption = document.querySelector('.mode-option input[value="integrated"]')?.closest(".mode-option");
    const legacyManualOption = document.querySelector('.mode-option input[value="manual"]')?.closest(".mode-option");
    const manualToggle = document.querySelector(".manual-v5-toggle");
    const legacyManualPanel = document.querySelector("#manual-panel");
    const manualPanel = document.querySelector("#chatgpt-manual-panel");
    const manualContinue = document.querySelector("#manual-v5-continue-current");

    setHidden(integratedOption, true);
    setHidden(legacyManualOption, true);
    setHidden(manualToggle, true);
    setHidden(legacyManualPanel, true);
    setHidden(manualPanel, true);
    setHidden(manualContinue, true);

    const selectedLegacy = document.querySelector(
      '.engine-selector input[name="engine-mode"]:checked:is([value="integrated"], [value="manual"])',
    );
    if (selectedLegacy) {
      const codex = document.querySelector('.engine-selector input[name="engine-mode"][value="codex"]');
      if (codex) {
        codex.checked = true;
        codex.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    const manualToggleInput = document.querySelector("#chatgpt-manual-enabled");
    if (manualToggleInput?.checked) {
      manualToggleInput.checked = false;
      manualToggleInput.dispatchEvent(new Event("change", { bubbles: true }));
    }
    document.body.classList.remove("manual-v5-enabled");
  }

  hideDefaultLegacyPaths();

  const panel = document.querySelector("#chatgpt-manual-panel");
  const importedSection = document.querySelector("#manual-v5-imported");
  if (!panel || !importedSection) {
    window.PSOSManualFocus = Object.freeze({
      version: 2,
      diagnosticMode,
      sync: hideDefaultLegacyPaths,
    });
    return;
  }

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

  function syncManualFocus() {
    hideDefaultLegacyPaths();
    if (!diagnosticMode) {
      setHidden(engineHeading, false);
      setHidden(engineSelector, false);
      completionNote.hidden = true;
      panel.classList.remove("manual-v5-completed");
      return;
    }

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
    version: 2,
    diagnosticMode,
    sync: syncManualFocus,
  });
})();
