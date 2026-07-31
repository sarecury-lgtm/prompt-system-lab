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
const DEFAULT_CORE_PROCEDURE = [
  "사용자의 요청에서 최종적으로 필요한 결과를 파악한다.",
  "요청에 포함된 조건과 제공 자료를 기준으로 실제 작업을 수행한다.",
  "결과를 검토하고 사용자가 바로 쓸 수 있는 최종 답을 제시한다.",
];
const DEFAULT_COMPLETION =
  "사용자가 요청한 결과가 바로 사용할 수 있는 형태로 제공된다.";

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

function simplifyRendererForm() {
  const goalLabel = fieldLabel(rendererElements.goal);
  const procedureLabel = fieldLabel(rendererElements.procedure);
  const constraintsLabel = fieldLabel(rendererElements.constraints);
  const completionLabel = fieldLabel(rendererElements.completion);
  const firstGrid = procedureLabel?.parentElement;

  rendererElements.intro.querySelector("strong").textContent =
    "평소에는 아래 한 칸만 쓰면 됩니다.";
  rendererElements.intro.querySelector("p").textContent =
    "만들고 싶은 프롬프트를 평소 말하듯 적으면 공통 PSOS 절차를 붙여 바로 생성합니다.";

  goalLabel.querySelector("span").textContent = "어떤 프롬프트가 필요한가요?";
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
    "세부 설정을 비우면 공통 기본 절차를 사용합니다. 모델 호출과 파일 변경은 없습니다.";
}

function updateEngineMode() {
  const deterministic = selectedEngineMode() === "deterministic";
  rendererElements.codexPanel.hidden = deterministic;
  rendererElements.rendererPanel.hidden = !deterministic;
  rendererElements.sectionNote.textContent = deterministic
    ? "요청 한 칸으로 모델 호출 없이 최종 프롬프트를 만듭니다."
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

  const customProcedure = splitLines(rendererElements.procedure.value);
  const customCompletion = rendererElements.completion.value.trim();

  rendererElements.submit.disabled = true;
  setResultState("running");
  elements.runningTitle.textContent = "프롬프트를 만들고 있습니다.";
  elements.runningDetail.textContent = "Codex와 모델 호출 없이 공통 PSOS 구조를 적용합니다.";
  try {
    const data = await requestJson("/api/render-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goal: request,
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
updateEngineMode();
