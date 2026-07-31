const rendererElements = {
  modes: document.querySelectorAll('input[name="engine-mode"]'),
  codexPanel: document.querySelector("#codex-panel"),
  rendererPanel: document.querySelector("#renderer-panel"),
  sectionNote: document.querySelector("#request-section-note"),
  form: document.querySelector("#renderer-form"),
  goal: document.querySelector("#renderer-goal"),
  procedure: document.querySelector("#renderer-procedure"),
  constraints: document.querySelector("#renderer-constraints"),
  completion: document.querySelector("#renderer-completion"),
  supporting: document.querySelector("#renderer-supporting"),
  exceptions: document.querySelector("#renderer-exceptions"),
  exclusions: document.querySelector("#renderer-exclusions"),
  upstream: document.querySelector("#renderer-upstream"),
  outputDetails: document.querySelector("#renderer-output-details"),
  submit: document.querySelector("#render-button"),
};

const engineStorageKey = "psos-engine-mode";

function selectedEngineMode() {
  return document.querySelector('input[name="engine-mode"]:checked')?.value || "codex";
}

function splitLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function updateEngineMode() {
  const deterministic = selectedEngineMode() === "deterministic";
  rendererElements.codexPanel.hidden = deterministic;
  rendererElements.rendererPanel.hidden = !deterministic;
  rendererElements.sectionNote.textContent = deterministic
    ? "모델 호출 없이 입력한 구조를 검증해 최종 프롬프트를 만듭니다."
    : "모델과 해결 방식은 시스템이 자동으로 고릅니다.";
  window.localStorage.setItem(engineStorageKey, deterministic ? "deterministic" : "codex");
  if (deterministic) rendererElements.goal.focus();
}

async function submitRenderer(event) {
  event.preventDefault();
  const goal = rendererElements.goal.value.trim();
  const coreProcedure = splitLines(rendererElements.procedure.value);
  const completion = rendererElements.completion.value.trim();
  if (!goal) {
    rendererElements.goal.focus();
    return;
  }
  if (!coreProcedure.length) {
    rendererElements.procedure.focus();
    return;
  }
  if (!completion) {
    rendererElements.completion.focus();
    return;
  }

  rendererElements.submit.disabled = true;
  setResultState("running");
  elements.runningTitle.textContent = "프롬프트 구조를 검증하고 있습니다.";
  elements.runningDetail.textContent = "Codex와 모델 호출 없이 즉시 렌더링합니다.";
  try {
    const data = await requestJson("/api/render-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goal,
        core_procedure: coreProcedure,
        fixed_constraints: splitLines(rendererElements.constraints.value),
        completion_condition: completion,
        supporting_inputs: splitLines(rendererElements.supporting.value),
        defaults_and_exceptions: splitLines(rendererElements.exceptions.value),
        exclusions: splitLines(rendererElements.exclusions.value),
        upstream_context: splitLines(rendererElements.upstream.value),
        output_details: splitLines(rendererElements.outputDetails.value),
      }),
    });
    showCompleted(data);
  } catch (error) {
    showError(error.message);
  } finally {
    rendererElements.submit.disabled = false;
  }
}

const savedEngine = window.localStorage.getItem(engineStorageKey);
const pendingCodexWork =
  window.sessionStorage.getItem("psos-active-job") ||
  window.sessionStorage.getItem("psos-pending-approval");
rendererElements.modes.forEach((mode) => {
  mode.checked = pendingCodexWork
    ? mode.value === "codex"
    : mode.value === (savedEngine || "codex");
  mode.addEventListener("change", updateEngineMode);
});
rendererElements.form.addEventListener("submit", submitRenderer);
updateEngineMode();
