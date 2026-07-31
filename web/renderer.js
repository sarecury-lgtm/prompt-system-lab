const rendererElements = {
  modes: document.querySelectorAll('input[name="engine-mode"]'),
  codexPanel: document.querySelector("#codex-panel"),
  rendererPanel: document.querySelector("#renderer-panel"),
  sectionNote: document.querySelector("#request-section-note"),
  form: document.querySelector("#renderer-form"),
  intro: document.querySelector(".renderer-intro"),
  goal: document.querySelector("#renderer-goal"),
  procedure: document.querySelector("#renderer-procedure"),
  constraints: document.querySelector("#renderer-constraints"),
  completion: document.querySelector("#renderer-completion"),
  supporting: document.querySelector("#renderer-supporting"),
  exceptions: document.querySelector("#renderer-exceptions"),
  exclusions: document.querySelector("#renderer-exclusions"),
  upstream: document.querySelector("#renderer-upstream"),
  outputDetails: document.querySelector("#renderer-output-details"),
  optional: document.querySelector(".renderer-optional"),
  optionalGrid: document.querySelector(".renderer-optional .optional-grid"),
  submit: document.querySelector("#render-button"),
};

const engineStorageKey = "psos-engine-mode";
const appliedPromptStorageKey = "psos-applied-fast-template";
const DEFAULT_CORE_PROCEDURE = [
  "사용자 요청에서 실제로 수행해야 할 작업과 최종 판단을 파악한다.",
  "제공된 자료와 조건만 사용해 요청한 작업을 직접 수행한다.",
  "핵심 근거, 주요 위험, 결론이 바뀌는 조건과 다음 행동을 포함해 바로 쓸 수 있는 결과를 제시한다.",
];
const DEFAULT_COMPLETION =
  "사용자가 요청한 실제 작업의 결과가 제공되며, 프롬프트를 다시 만들라고 요구하지 않는다.";

function selectedEngineMode() {
  return document.querySelector('input[name="engine-mode"]:checked')?.value || "codex";
}

function splitLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function fieldLabel(input) {
  return input?.closest(".field-label") || null;
}

function normalizePromptGoal(value) {
  let cleaned = String(value || "").trim();
  if (!cleaned) return "";

  const directTask = cleaned.replace(
    /\s*(?:하는|해주는|해 줄|해줄)\s+프롬프트(?:를|을)?\s*(?:만들어|작성해|생성해)\s*(?:줘|주세요)?[.!?]?$/u,
    "한다.",
  );
  if (directTask !== cleaned) return directTask;

  const withoutPromptRequest = cleaned.replace(
    /\s*프롬프트(?:를|을)?\s*(?:만들어|작성해|생성해)\s*(?:줘|주세요)?[.!?]?$/u,
    "",
  ).trim();
  if (withoutPromptRequest !== cleaned && withoutPromptRequest) {
    return /[.!?]$/.test(withoutPromptRequest)
      ? withoutPromptRequest
      : `${withoutPromptRequest} 작업을 수행한다.`;
  }
  return cleaned;
}

function clearRendererResultActions() {
  document.querySelector("#renderer-result-actions")?.remove();
}

function renderRendererResultActions(promptText) {
  clearRendererResultActions();
  const completed = document.querySelector("#completed-result");
  if (!completed || !promptText) return;

  const actions = document.createElement("div");
  actions.id = "renderer-result-actions";
  actions.className = "request-actions renderer-actions";

  const status = document.createElement("span");
  status.className = "renderer-proof";
  status.textContent = "복사용 초안 · 아직 실행에 적용되지 않음";

  const buttons = document.createElement("div");
  buttons.className = "approval-actions";

  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "secondary-button";
  copyButton.textContent = "복사";
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      status.textContent = "클립보드에 복사했습니다.";
    } catch (_error) {
      status.textContent = "자동 복사에 실패했습니다. 결과를 직접 선택해 복사해 주세요.";
    }
  });

  const applyButton = document.createElement("button");
  applyButton.type = "button";
  applyButton.className = "secondary-button";
  applyButton.textContent = "다음 Codex 요청에 1회 적용";
  applyButton.addEventListener("click", () => {
    window.localStorage.setItem(appliedPromptStorageKey, promptText);
    rendererElements.modes.forEach((mode) => {
      mode.checked = mode.value === "codex";
    });
    updateEngineMode();
    elements.request.placeholder =
      "실제 요청을 입력하세요. 방금 만든 템플릿이 다음 실행에 한 번만 적용됩니다.";
    elements.request.focus();
    status.textContent = "다음 Codex 요청에 한 번 적용됩니다.";
  });

  buttons.append(copyButton, applyButton);
  actions.append(status, buttons);
  completed.appendChild(actions);
}

function applyStoredPromptToNextCodexRequest() {
  const promptText = window.localStorage.getItem(appliedPromptStorageKey);
  const userRequest = elements.request.value.trim();
  if (!promptText || !userRequest) return;
  elements.request.value = `${promptText}\n\n[현재 사용자 요청]\n${userRequest}`;
  window.localStorage.removeItem(appliedPromptStorageKey);
  clearRendererResultActions();
}

function simplifyRendererForm() {
  const goalLabel = fieldLabel(rendererElements.goal);
  const procedureLabel = fieldLabel(rendererElements.procedure);
  const constraintsLabel = fieldLabel(rendererElements.constraints);
  const completionLabel = fieldLabel(rendererElements.completion);
  const firstGrid = procedureLabel?.parentElement;
  const deterministicMode = Array.from(rendererElements.modes)
    .find((mode) => mode.value === "deterministic");
  const deterministicLabel = deterministicMode?.closest(".mode-option");

  if (deterministicLabel) {
    deterministicLabel.querySelector("strong").textContent = "빠른 템플릿 생성";
    deterministicLabel.querySelector("small").textContent =
      "AI 설계 없이 공통 틀로 복사용 초안을 즉시 만듭니다.";
  }

  rendererElements.intro.querySelector("strong").textContent =
    "빠른 복사용 초안입니다.";
  rendererElements.intro.querySelector("p").textContent =
    "전문 설계 단계는 거치지 않습니다. 요청 한 칸으로 공통 PSOS 틀을 붙이고, 필요하면 다음 Codex 실행에 한 번 적용할 수 있습니다.";

  goalLabel.querySelector("span").textContent = "어떤 작업용 템플릿이 필요한가요?";
  rendererElements.goal.rows = 7;
  rendererElements.goal.placeholder =
    "예: 첨부한 여러 시간대 차트를 보고 지금 진입할지, 손절과 분할익절을 어떻게 할지 판단하는 프롬프트를 만들어 줘.";

  constraintsLabel.querySelector("span").textContent = "꼭 지킬 조건 · 선택";
  rendererElements.constraints.rows = 3;
  rendererElements.constraints.placeholder =
    "예: 차트에서 확인되지 않는 사실은 만들지 않는다.\n하나의 현재 판단을 분명히 제시한다.";

  procedureLabel.querySelector("span").textContent = "핵심 절차 직접 지정 · 선택";
  completionLabel.querySelector("span").textContent = "완료 조건 직접 지정 · 선택";
  rendererElements.procedure.removeAttribute("required");
  rendererElements.completion.removeAttribute("required");

  if (firstGrid && constraintsLabel && goalLabel) {
    goalLabel.after(constraintsLabel);
    firstGrid.remove();
  }
  if (rendererElements.optionalGrid) {
    rendererElements.optionalGrid.prepend(procedureLabel, completionLabel);
  }
  rendererElements.optional.querySelector("summary").textContent =
    "세부 설정 · 필요할 때만";

  const safety = rendererElements.form.querySelector(".safety-note");
  safety.textContent =
    "생성 결과는 자동 실행되지 않습니다. 복사하거나 다음 Codex 요청에 1회 적용할 수 있습니다.";
}

function updateEngineMode() {
  const deterministic = selectedEngineMode() === "deterministic";
  rendererElements.codexPanel.hidden = deterministic;
  rendererElements.rendererPanel.hidden = !deterministic;
  rendererElements.sectionNote.textContent = deterministic
    ? "AI 설계 없이 공통 틀로 복사용 초안을 즉시 만듭니다."
    : "모델과 해결 방식은 시스템이 자동으로 고릅니다.";
  window.localStorage.setItem(engineStorageKey, deterministic ? "deterministic" : "codex");
  if (deterministic) rendererElements.goal.focus();
}

async function submitRenderer(event) {
  event.preventDefault();
  const request = rendererElements.goal.value.trim();
  if (!request) {
    rendererElements.goal.focus();
    return;
  }

  const normalizedGoal = normalizePromptGoal(request);
  const customProcedure = splitLines(rendererElements.procedure.value);
  const customCompletion = rendererElements.completion.value.trim();

  clearRendererResultActions();
  rendererElements.submit.disabled = true;
  setResultState("running");
  elements.runningTitle.textContent = "빠른 템플릿을 만들고 있습니다.";
  elements.runningDetail.textContent = "Codex와 모델 호출 없이 공통 PSOS 구조를 적용합니다.";
  try {
    const data = await requestJson("/api/render-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goal: normalizedGoal,
        core_procedure: customProcedure.length
          ? customProcedure
          : DEFAULT_CORE_PROCEDURE,
        fixed_constraints: splitLines(rendererElements.constraints.value),
        completion_condition: customCompletion || DEFAULT_COMPLETION,
        supporting_inputs: splitLines(rendererElements.supporting.value),
        defaults_and_exceptions: splitLines(rendererElements.exceptions.value),
        exclusions: splitLines(rendererElements.exclusions.value),
        upstream_context: splitLines(rendererElements.upstream.value),
        output_details: splitLines(rendererElements.outputDetails.value),
      }),
    });
    showCompleted(data);
    renderRendererResultActions(data.result_markdown);
  } catch (error) {
    showError(error.message);
  } finally {
    rendererElements.submit.disabled = false;
  }
}

simplifyRendererForm();
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
document.querySelector("#request-form")?.addEventListener(
  "submit",
  applyStoredPromptToNextCodexRequest,
  true,
);
updateEngineMode();
