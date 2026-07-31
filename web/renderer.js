const promptUi = {
  modes: document.querySelectorAll('input[name="engine-mode"]'),
  codexPanel: document.querySelector("#codex-panel"),
  integratedPanel: document.querySelector("#renderer-panel"),
  manualPanel: null,
  sectionNote: document.querySelector("#request-section-note"),
  form: document.querySelector("#renderer-form"),
  intro: document.querySelector(".renderer-intro"),
  request: document.querySelector("#renderer-goal"),
  procedure: document.querySelector("#renderer-procedure"),
  constraints: document.querySelector("#renderer-constraints"),
  completion: document.querySelector("#renderer-completion"),
  optional: document.querySelector(".renderer-optional"),
  submit: document.querySelector("#render-button"),
};

const engineStorageKey = "psos-engine-mode";
const appliedPromptStorageKey = "psos-applied-prompt";
const latestIntegratedPromptStorageKey = "psos-latest-integrated-prompt";
const latestIntegratedRequestStorageKey = "psos-latest-integrated-request";
const manualStateStorageKey = "psos-manual-workflow-state";

function selectedEngineMode() {
  return document.querySelector('input[name="engine-mode"]:checked')?.value || "codex";
}

function fieldLabel(input) {
  return input?.closest(".field-label") || null;
}

async function copyText(text, statusElement, successText = "복사했습니다.") {
  if (!String(text || "").trim()) {
    statusElement.textContent = "먼저 필요한 내용을 입력해 주세요.";
    return false;
  }
  try {
    await navigator.clipboard.writeText(text);
    statusElement.textContent = successText;
    return true;
  } catch (_error) {
    statusElement.textContent = "자동 복사에 실패했습니다. 내용을 직접 선택해 복사해 주세요.";
    return false;
  }
}

function queuePromptForNextCodexRequest(promptText, statusElement) {
  if (!String(promptText || "").trim()) {
    statusElement.textContent = "적용할 프롬프트가 없습니다.";
    return;
  }
  window.localStorage.setItem(appliedPromptStorageKey, promptText);
  promptUi.modes.forEach((mode) => {
    mode.checked = mode.value === "codex";
  });
  updateEngineMode();
  elements.request.placeholder =
    "실제 요청을 입력하세요. 선택한 프롬프트가 다음 실행에 한 번만 적용됩니다.";
  elements.request.focus();
  statusElement.textContent = "다음 Codex 요청에 한 번 적용됩니다.";
}

function applyStoredPromptToNextCodexRequest() {
  const promptText = window.localStorage.getItem(appliedPromptStorageKey);
  const userRequest = elements.request.value.trim();
  if (!promptText || !userRequest) return;
  elements.request.value = `${promptText}\n\n[현재 사용자 요청]\n${userRequest}`;
  window.localStorage.removeItem(appliedPromptStorageKey);
  document.querySelector("#prompt-result-actions")?.remove();
}

function renderPromptResultActions(promptText, label) {
  document.querySelector("#prompt-result-actions")?.remove();
  const completed = document.querySelector("#completed-result");
  if (!completed || !promptText) return;

  const actions = document.createElement("div");
  actions.id = "prompt-result-actions";
  actions.className = "request-actions renderer-actions";

  const status = document.createElement("span");
  status.className = "renderer-proof";
  status.textContent = label;

  const buttons = document.createElement("div");
  buttons.className = "approval-actions";

  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "secondary-button";
  copyButton.textContent = "복사";
  copyButton.addEventListener("click", () => {
    copyText(promptText, status, "클립보드에 복사했습니다.");
  });

  const applyButton = document.createElement("button");
  applyButton.type = "button";
  applyButton.className = "secondary-button";
  applyButton.textContent = "다음 Codex 요청에 1회 적용";
  applyButton.addEventListener("click", () => {
    queuePromptForNextCodexRequest(promptText, status);
  });

  buttons.append(copyButton, applyButton);
  actions.append(status, buttons);
  completed.appendChild(actions);
}

function routerPrompt(request) {
  return `당신은 Personal Problem-Solving OS의 라우터다.

사용자 요청의 상위 목적과 고정 조건을 보존하고 Goal Ledger를 작성한 뒤, 가장 작은 충분 해결 경로만 선택한다. 이 단계에서는 답변·검색·프롬프트·코드 결과를 만들지 않는다.

[경로]
- DIRECT: 파일 시스템 변경 없이 현재 지식과 제공 문맥으로 바로 답할 수 있음
- RESEARCH: 최신성·실재성·공식 출처가 결과를 바꿈
- REUSE: 승인된 범위의 기존 자산·도구·템플릿을 실제로 확인해야 함
- PROMPT: 다른 AI나 별도 환경에서 반복 사용할 지침 자체가 산출물
- CODE: 실제 파일 생성·수정 또는 반복·재현성·대량 처리 때문에 코드 실행이 필요
- PROJECT: 여러 단계·파일·상태 유지가 정말 필요
- HYBRID: 주 경로 하나와 보조 경로 하나가 모두 필요

[선택 규칙]
1. 단순 요청을 CODE·PROJECT·HYBRID로 키우지 않는다.
2. 최신 사실이나 실재 여부가 결과를 바꾸면 RESEARCH를 선택한다.
3. 재사용 가능한 지침 자체가 필요하면 PROMPT를 선택한다.
4. 사용자의 표현보다 실제 상위 목적을 보존한다.
5. 내부 추론은 노출하지 않는다.

다음 필드를 가진 JSON 객체 하나만 반환한다.
parent_goal, current_goal_hypothesis, fixed_constraints, current_position, selected_route, secondary_route, route_reason, current_step, why_this_step_matters, completion_condition, important_uncertainties

[사용자 요청]
${request.trim()}`;
}

function briefCompilerPrompt(request, ledger) {
  return `당신은 Personal Problem-Solving OS의 Prompt Build Brief 컴파일러다.

최종 프롬프트를 작성하지 않는다. 사용자 요청과 Goal Ledger를 하나의 짧은 작업 계약으로 통합한다.

[컴파일 원칙]
1. goal은 최종 프롬프트가 다른 AI에게 실제로 수행시킬 일을 쓴다.
2. core_procedure는 그 AI가 실행할 도메인 작업의 판단·처리 순서다. 프롬프트 작성 절차를 쓰지 않는다.
3. supporting_inputs에는 핵심 절차를 돕는 자료·분석 요소·도구만 둔다.
4. 같은 의미의 요구는 하나로 합친다.
5. fixed_constraints는 Goal Ledger의 fixed_constraints를 문구와 순서까지 정확히 복사한다.
6. output_contract의 첫 항목은 Goal Ledger completion_condition을 정확히 복사한다.
7. defaults_and_exceptions에는 결과를 바꾸는 누락 처리만 둔다.
8. exclusions에는 목표를 벗어나는 작업만 둔다.
9. 내부 추론을 노출하지 말고 JSON 객체 하나만 반환한다.

다음 필드를 사용한다.
version, goal, core_procedure, supporting_inputs, fixed_constraints, output_contract, defaults_and_exceptions, exclusions, upstream_context

[사용자 요청]
${request.trim()}

[Goal Ledger]
${ledger.trim()}`;
}

function finalExecutorPrompt(brief) {
  return `당신은 Personal Problem-Solving OS의 PROMPT 실행기다.

아래 Prompt Build Brief를 유일한 사용자 요구 표면으로 사용해, 다른 AI가 반복 실행할 최종 프롬프트 하나를 완성한다.

[작성 원칙]
1. 목표와 고정 조건은 의미를 보존하되 같은 표현을 반복하지 않는다.
2. 핵심 작업 절차를 프롬프트의 중심에 둔다.
3. 같은 의미가 원칙·절차·출력 형식에서 되풀이되면 하나로 합친다.
4. 출력 형식은 사용자가 판단하거나 행동하는 데 필요한 최소 구조만 둔다.
5. 정보가 충분하면 불필요한 질문 없이 진행하고, 결론이 크게 달라질 때만 질문 1~2개를 허용한다.
6. 사용자의 원하는 결론보다 근거와 실패 위험을 우선한다.
7. 내부 추론이나 PSOS 생성 과정을 노출하지 않는다.
8. 설명이나 JSON 포장 없이 최종 프롬프트 본문만 반환한다.

[Prompt Build Brief]
${brief.trim()}`;
}

function loadManualState() {
  try {
    const value = JSON.parse(window.localStorage.getItem(manualStateStorageKey) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch (_error) {
    return {};
  }
}

function saveManualState(fields) {
  const value = {};
  Object.entries(fields).forEach(([key, field]) => {
    value[key] = field.value;
  });
  window.localStorage.setItem(manualStateStorageKey, JSON.stringify(value));
}

function createManualStep(number, title, description, textareaId, placeholder) {
  const section = document.createElement("section");
  section.className = "manual-step";

  const heading = document.createElement("div");
  heading.className = "manual-step-heading";
  const label = document.createElement("span");
  label.className = "step-label";
  label.textContent = `${String(number).padStart(2, "0")} · 수동 단계`;
  const name = document.createElement("h3");
  name.textContent = title;
  const note = document.createElement("p");
  note.textContent = description;
  heading.append(label, name, note);

  const textarea = document.createElement("textarea");
  textarea.id = textareaId;
  textarea.rows = number === 1 ? 5 : 9;
  textarea.placeholder = placeholder;

  const actions = document.createElement("div");
  actions.className = "request-actions manual-step-actions";
  const status = document.createElement("span");
  status.className = "renderer-proof";
  const buttonBox = document.createElement("div");
  buttonBox.className = "approval-actions";
  actions.append(status, buttonBox);

  section.append(heading, textarea, actions);
  return { section, textarea, status, buttonBox };
}

function combinedComparisonText(integrated, manual) {
  return `# 통합 AI 1회 결과\n\n${integrated.trim()}\n\n---\n\n# 수동 PSOS 4단계 결과\n\n${manual.trim()}`;
}

function buildManualPanel() {
  const panel = document.createElement("div");
  panel.id = "manual-panel";
  panel.className = "renderer-panel manual-panel";
  panel.hidden = true;

  const intro = document.createElement("div");
  intro.className = "renderer-intro";
  intro.innerHTML = "<strong>예전 수동 PSOS 4단계</strong><p>각 단계 지시문을 복사해 AI에 보내고 결과를 다음 칸에 붙입니다. 마지막에는 통합 AI 1회 결과와 함께 복사할 수 있습니다.</p>";

  const form = document.createElement("div");
  form.className = "request-form renderer-form manual-form";

  const requestStep = createManualStep(
    1,
    "원래 요청",
    "비교할 요청을 적고 라우터 지시문을 복사합니다.",
    "manual-request",
    "예: 첨부한 여러 시간대 차트를 보고 지금 진입할지, 손절과 분할익절을 어떻게 할지 판단하는 프롬프트를 만들어 줘.",
  );
  const requestCopy = document.createElement("button");
  requestCopy.type = "button";
  requestCopy.className = "secondary-button";
  requestCopy.textContent = "1단계 라우터 지시문 복사";
  requestStep.buttonBox.appendChild(requestCopy);

  const ledgerStep = createManualStep(
    2,
    "Goal Ledger 결과",
    "AI가 반환한 Goal Ledger JSON을 붙이고 Brief 컴파일러 지시문을 복사합니다.",
    "manual-ledger",
    "1단계에서 받은 Goal Ledger JSON을 붙여 넣으세요.",
  );
  const ledgerCopy = document.createElement("button");
  ledgerCopy.type = "button";
  ledgerCopy.className = "secondary-button";
  ledgerCopy.textContent = "2단계 Brief 컴파일러 복사";
  ledgerStep.buttonBox.appendChild(ledgerCopy);

  const briefStep = createManualStep(
    3,
    "Prompt Build Brief 결과",
    "AI가 반환한 Brief JSON을 붙이고 최종 실행기 지시문을 복사합니다.",
    "manual-brief",
    "2단계에서 받은 Prompt Build Brief JSON을 붙여 넣으세요.",
  );
  const briefCopy = document.createElement("button");
  briefCopy.type = "button";
  briefCopy.className = "secondary-button";
  briefCopy.textContent = "3단계 최종 실행기 복사";
  briefStep.buttonBox.appendChild(briefCopy);

  const finalStep = createManualStep(
    4,
    "수동 PSOS 최종 프롬프트",
    "3단계에서 나온 최종 프롬프트를 붙이면 복사·적용·비교가 가능합니다.",
    "manual-final",
    "3단계에서 생성된 최종 프롬프트를 붙여 넣으세요.",
  );
  const finalCopy = document.createElement("button");
  finalCopy.type = "button";
  finalCopy.className = "secondary-button";
  finalCopy.textContent = "최종 프롬프트 복사";
  const finalApply = document.createElement("button");
  finalApply.type = "button";
  finalApply.className = "secondary-button";
  finalApply.textContent = "다음 Codex 요청에 1회 적용";
  finalStep.buttonBox.append(finalCopy, finalApply);

  const compare = document.createElement("section");
  compare.className = "manual-compare";
  const compareHeading = document.createElement("div");
  compareHeading.className = "manual-step-heading";
  compareHeading.innerHTML = "<span class=\"step-label\">비교용 복사</span><h3>통합 AI 1회 + 수동 PSOS 4단계</h3><p>두 결과를 함께 복사해 ChatGPT에 붙여 비교합니다.</p>";

  const compareGrid = document.createElement("div");
  compareGrid.className = "renderer-grid manual-compare-grid";
  const integratedLabel = document.createElement("label");
  integratedLabel.className = "field-label";
  integratedLabel.innerHTML = "<span>최근 통합 AI 1회 결과</span>";
  const integratedResult = document.createElement("textarea");
  integratedResult.id = "manual-integrated-result";
  integratedResult.rows = 14;
  integratedResult.readOnly = true;
  integratedResult.placeholder = "통합 AI 1회 모드에서 먼저 생성하면 여기에 표시됩니다.";
  integratedLabel.appendChild(integratedResult);

  const manualLabel = document.createElement("label");
  manualLabel.className = "field-label";
  manualLabel.innerHTML = "<span>수동 PSOS 최종 결과</span>";
  const manualResult = document.createElement("textarea");
  manualResult.id = "manual-compare-final";
  manualResult.rows = 14;
  manualResult.readOnly = true;
  manualLabel.appendChild(manualResult);
  compareGrid.append(integratedLabel, manualLabel);

  const compareActions = document.createElement("div");
  compareActions.className = "request-actions manual-step-actions";
  const compareStatus = document.createElement("span");
  compareStatus.className = "renderer-proof";
  const copyBoth = document.createElement("button");
  copyBoth.type = "button";
  copyBoth.className = "secondary-button compare-copy-button";
  copyBoth.textContent = "두 결과 같이 복사";
  compareActions.append(compareStatus, copyBoth);
  compare.append(compareHeading, compareGrid, compareActions);

  form.append(
    intro,
    requestStep.section,
    ledgerStep.section,
    briefStep.section,
    finalStep.section,
    compare,
  );
  panel.appendChild(form);

  const state = loadManualState();
  const fields = {
    request: requestStep.textarea,
    ledger: ledgerStep.textarea,
    brief: briefStep.textarea,
    final: finalStep.textarea,
  };
  Object.entries(fields).forEach(([key, field]) => {
    field.value = state[key] || "";
    field.addEventListener("input", () => {
      saveManualState(fields);
      manualResult.value = finalStep.textarea.value;
    });
  });
  if (!requestStep.textarea.value) {
    requestStep.textarea.value = window.localStorage.getItem(latestIntegratedRequestStorageKey) || "";
  }
  integratedResult.value = window.localStorage.getItem(latestIntegratedPromptStorageKey) || "";
  manualResult.value = finalStep.textarea.value;

  requestCopy.addEventListener("click", () => {
    copyText(
      routerPrompt(requestStep.textarea.value),
      requestStep.status,
      "라우터 지시문을 복사했습니다. AI에 보내고 결과를 2단계에 붙여 넣으세요.",
    );
  });
  ledgerCopy.addEventListener("click", () => {
    if (!requestStep.textarea.value.trim() || !ledgerStep.textarea.value.trim()) {
      ledgerStep.status.textContent = "원래 요청과 Goal Ledger 결과를 먼저 입력해 주세요.";
      return;
    }
    copyText(
      briefCompilerPrompt(requestStep.textarea.value, ledgerStep.textarea.value),
      ledgerStep.status,
      "Brief 컴파일러 지시문을 복사했습니다. 결과를 3단계에 붙여 넣으세요.",
    );
  });
  briefCopy.addEventListener("click", () => {
    if (!briefStep.textarea.value.trim()) {
      briefStep.status.textContent = "Prompt Build Brief 결과를 먼저 입력해 주세요.";
      return;
    }
    copyText(
      finalExecutorPrompt(briefStep.textarea.value),
      briefStep.status,
      "최종 실행기 지시문을 복사했습니다. 결과를 4단계에 붙여 넣으세요.",
    );
  });
  finalCopy.addEventListener("click", () => {
    copyText(finalStep.textarea.value, finalStep.status, "최종 프롬프트를 복사했습니다.");
  });
  finalApply.addEventListener("click", () => {
    queuePromptForNextCodexRequest(finalStep.textarea.value, finalStep.status);
  });
  copyBoth.addEventListener("click", () => {
    if (!integratedResult.value.trim() || !manualResult.value.trim()) {
      compareStatus.textContent = "통합 AI 결과와 수동 최종 결과를 모두 준비해 주세요.";
      return;
    }
    copyText(
      combinedComparisonText(integratedResult.value, manualResult.value),
      compareStatus,
      "두 결과를 한 번에 복사했습니다.",
    );
  });

  return panel;
}

function installManualMode() {
  const selector = document.querySelector(".engine-selector");
  if (!selector || selector.querySelector('input[value="manual"]')) return;

  const option = document.createElement("label");
  option.className = "mode-option";
  option.innerHTML = `
    <input type="radio" name="engine-mode" value="manual">
    <span>
      <strong>수동 PSOS 4단계</strong>
      <small>예전처럼 네 번 옮겨 붙여 만든 결과입니다.</small>
    </span>`;
  selector.appendChild(option);

  promptUi.manualPanel = buildManualPanel();
  promptUi.integratedPanel.after(promptUi.manualPanel);
  promptUi.modes = document.querySelectorAll('input[name="engine-mode"]');
}

function configureIntegratedMode() {
  const integratedMode = Array.from(promptUi.modes).find((mode) => mode.value === "deterministic");
  if (integratedMode) {
    integratedMode.value = "integrated";
    const option = integratedMode.closest(".mode-option");
    option.querySelector("strong").textContent = "통합 AI 1회";
    option.querySelector("small").textContent =
      "Goal Ledger와 Brief를 한 번에 만들고 로컬에서 최종 조립합니다.";
  }

  promptUi.intro.querySelector("strong").textContent = "논리 단계는 유지하고 AI 호출만 한 번으로 합칩니다.";
  promptUi.intro.querySelector("p").textContent =
    "Codex가 Goal Ledger와 Prompt Build Brief를 한 번에 설계하고, 검증된 결과를 로컬 렌더러가 즉시 최종 프롬프트로 조립합니다.";

  const requestLabel = fieldLabel(promptUi.request);
  requestLabel.querySelector("span").textContent = "어떤 프롬프트가 필요한가요?";
  promptUi.request.rows = 7;
  promptUi.request.placeholder =
    "예: 첨부한 여러 시간대 차트를 보고 지금 진입할지, 손절과 분할익절을 어떻게 할지 판단하는 프롬프트를 만들어 줘.";

  [promptUi.procedure, promptUi.constraints, promptUi.completion].forEach((field) => {
    const label = fieldLabel(field);
    if (label) label.hidden = true;
    field?.removeAttribute("required");
  });
  if (promptUi.optional) promptUi.optional.hidden = true;

  const proof = promptUi.form.querySelector(".renderer-proof");
  proof.textContent = "Codex 1회 · 로컬 검증 및 조립";
  promptUi.submit.querySelector("span:first-child").textContent = "AI 1회로 생성";
  promptUi.form.querySelector(".safety-note").textContent =
    "통합 모드는 Codex를 정확히 한 번 호출합니다. 최종 조립 단계에서는 모델을 다시 부르지 않습니다.";
}

function updateEngineMode() {
  const mode = selectedEngineMode();
  promptUi.codexPanel.hidden = mode !== "codex";
  promptUi.integratedPanel.hidden = mode !== "integrated";
  if (promptUi.manualPanel) promptUi.manualPanel.hidden = mode !== "manual";

  promptUi.sectionNote.textContent = mode === "integrated"
    ? "Goal Ledger와 Brief를 한 번에 설계한 뒤 로컬에서 최종 조립합니다."
    : mode === "manual"
      ? "예전 4단계 결과를 만든 뒤 두 결과를 함께 복사해 비교합니다."
      : "모델과 해결 방식은 시스템이 자동으로 고릅니다.";
  window.localStorage.setItem(engineStorageKey, mode);
  if (mode === "integrated") promptUi.request.focus();
  if (mode === "manual") document.querySelector("#manual-request")?.focus();
}

async function submitIntegratedPrompt(event) {
  event.preventDefault();
  const request = promptUi.request.value.trim();
  if (!request) {
    promptUi.request.focus();
    return;
  }

  document.querySelector("#prompt-result-actions")?.remove();
  promptUi.submit.disabled = true;
  setResultState("running");
  elements.runningTitle.textContent = "Goal Ledger와 Brief를 함께 설계하고 있습니다.";
  elements.runningDetail.textContent = "Codex를 한 번 호출한 뒤 로컬 렌더러가 최종 프롬프트를 조립합니다.";
  try {
    const data = await requestJson("/api/design-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request }),
    });
    window.localStorage.setItem(latestIntegratedPromptStorageKey, data.result_markdown);
    window.localStorage.setItem(latestIntegratedRequestStorageKey, request);
    const integratedCompare = document.querySelector("#manual-integrated-result");
    if (integratedCompare) integratedCompare.value = data.result_markdown;
    const manualRequest = document.querySelector("#manual-request");
    if (manualRequest && !manualRequest.value.trim()) manualRequest.value = request;
    showCompleted(data);
    renderPromptResultActions(data.result_markdown, "통합 AI 1회 결과 · 복사 또는 1회 적용 가능");
  } catch (error) {
    showError(error.message);
  } finally {
    promptUi.submit.disabled = false;
  }
}

configureIntegratedMode();
installManualMode();

const savedEngine = window.localStorage.getItem(engineStorageKey);
const normalizedSavedEngine = savedEngine === "deterministic" ? "integrated" : savedEngine;
const pendingCodexWork =
  window.sessionStorage.getItem("psos-active-job") ||
  window.sessionStorage.getItem("psos-pending-approval");
promptUi.modes.forEach((mode) => {
  mode.checked = pendingCodexWork
    ? mode.value === "codex"
    : mode.value === (normalizedSavedEngine || "codex");
  mode.addEventListener("change", updateEngineMode);
});
promptUi.form.addEventListener("submit", submitIntegratedPrompt);
document.querySelector("#request-form")?.addEventListener(
  "submit",
  applyStoredPromptToNextCodexRequest,
  true,
);
updateEngineMode();
