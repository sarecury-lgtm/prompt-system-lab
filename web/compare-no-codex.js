(() => {
  const integratedMode = document.querySelector('input[name="engine-mode"][value="integrated"]');
  const form = document.querySelector("#renderer-form");
  const requestField = document.querySelector("#renderer-goal");
  const designField = document.querySelector("#renderer-procedure");
  const constraintsField = document.querySelector("#renderer-constraints");
  const completionField = document.querySelector("#renderer-completion");
  const optional = document.querySelector(".renderer-optional");
  const submitButton = document.querySelector("#render-button");
  const sectionNote = document.querySelector("#request-section-note");
  const intro = document.querySelector(".renderer-intro");
  const engineStorageKey = "psos-engine-mode";
  const latestPromptKey = "psos-latest-integrated-prompt";
  const latestRequestKey = "psos-latest-integrated-request";
  const chatGptNewChatUrl = "https://chatgpt.com/";
  const copyTimers = new WeakMap();

  if (!integratedMode || !form || !requestField || !designField || !submitButton) return;

  function closestLabel(field) {
    return field?.closest(".field-label") || null;
  }

  function integratedInstruction(request) {
    return `당신은 Personal Problem-Solving OS의 통합 프롬프트 설계기이자 최종 편집기다.

사용자의 요청을 한 번만 분석해 다음 세 논리 단계를 내부에서 순서대로 수행한다.

1. 재사용 가능한 프롬프트 제작에 필요한 Goal Ledger를 작성한다.
2. 그 Goal Ledger를 기준으로 Prompt Build Brief를 작성한다.
3. 두 설계 결과를 바탕으로 실제 실행에 바로 쓸 최종 프롬프트를 작성한다.

설명이나 마크다운 코드블록 없이 아래 구조의 JSON 객체 하나만 출력한다.

[Goal Ledger 규칙]
1. 사용자가 궁극적으로 얻으려는 결과를 parent_goal에 쓴다.
2. current_goal_hypothesis는 최종 프롬프트가 다른 AI에게 실제로 수행시킬 작업으로 쓴다. “프롬프트를 만든다”를 작업 목표로 남기지 않는다.
3. fixed_constraints에는 사용자가 명시했거나 결과를 실질적으로 바꾸는 조건만 둔다.
4. 이 요청은 프롬프트 제작 전용이므로 selected_route는 반드시 PROMPT, secondary_route는 null로 둔다.
5. completion_condition은 사용자가 최종 프롬프트를 실행해 원하는 결과를 얻었는지 판별할 수 있게 쓴다.
6. important_uncertainties는 결과를 실제로 바꿀 수 있는 것만 최대 3개로 둔다.

[Prompt Build Brief 규칙]
1. goal은 Goal Ledger의 목적을 실제 수행 작업으로 구체화한다.
2. core_procedure는 범용 문구가 아니라 해당 도메인에서 판단과 결과를 좌우하는 구체적인 처리 순서로 작성한다.
3. core_procedure는 서로 다른 판단 단계를 합치지 말고 필요한 만큼 작성하되 12개를 넘기지 않는다.
4. supporting_inputs에는 절차 수행에 필요한 자료, 입력 형태, 분석 요소, 도구만 둔다.
5. fixed_constraints는 Goal Ledger의 fixed_constraints를 문구와 순서까지 정확히 복사한다.
6. output_contract의 첫 항목은 Goal Ledger의 completion_condition과 정확히 같아야 한다.
7. 나머지 output_contract에는 사용자가 실제로 비교·판단·행동하는 데 필요한 산출물만 둔다.
8. defaults_and_exceptions에는 누락 정보 처리처럼 결과가 달라지는 기본값만 둔다.
9. exclusions에는 목표 밖의 작업만 둔다.
10. 같은 의미를 여러 필드에 반복하지 않는다.
11. core_procedure를 “요청 파악 → 작업 수행 → 결과 제시” 같은 범용 절차로 끝내지 않는다.

[최종 프롬프트 편집 규칙]
1. final_prompt에는 다른 AI에 복사해 바로 실행할 프롬프트 본문만 쓴다.
2. Goal Ledger와 Prompt Build Brief는 내부 설계 자료로만 사용하고, 그 이름·필드·라우팅·설계 계약·PSOS 생성 과정은 final_prompt에 노출하지 않는다.
3. Brief의 필드를 순서대로 기계적으로 펼치지 말고 역할, 입력, 핵심 절차, 예외·제한, 출력 형식처럼 실제 실행에 필요한 구조로 다시 편집한다.
4. 같은 의미의 규칙은 합치고, 범용 운영 원칙은 도메인 작업의 판단이나 결과를 실제로 바꿀 때만 남긴다.
5. core_procedure의 도메인 판단 단계, fixed_constraints, completion_condition과 필요한 output_contract는 빠뜨리지 않는다.
6. 최종 프롬프트가 다시 “프롬프트를 만들어라”고 요구하지 않게 하고 사용자가 원한 실제 작업을 직접 수행하게 한다.
7. 길이를 늘리는 것보다 실행의 명확성, 도메인 집중도, 중복 제거와 출력 일관성을 우선한다.
8. final_prompt는 마크다운 제목과 목록을 사용할 수 있지만 JSON 안의 하나의 문자열 값으로 반환한다.

[출력 JSON 구조]
{
  "goal_ledger": {
    "parent_goal": "...",
    "current_goal_hypothesis": "...",
    "fixed_constraints": [],
    "current_position": "...",
    "selected_route": "PROMPT",
    "secondary_route": null,
    "route_reason": "...",
    "current_step": "...",
    "why_this_step_matters": "...",
    "completion_condition": "...",
    "important_uncertainties": []
  },
  "prompt_build_brief": {
    "version": 1,
    "goal": "...",
    "core_procedure": [],
    "supporting_inputs": [],
    "fixed_constraints": [],
    "output_contract": [],
    "defaults_and_exceptions": [],
    "exclusions": [],
    "upstream_context": []
  },
  "final_prompt": "다른 AI에 그대로 복사해 실행할 최종 프롬프트 본문"
}

[사용자 요청]
${request.trim()}`;
  }

  function nearbyStatus(button) {
    return button?.closest(".request-actions")?.querySelector(".renderer-proof") || null;
  }

  function showCopied(button, originalLabel) {
    if (!button) return;
    const previousTimer = copyTimers.get(button);
    if (previousTimer) window.clearTimeout(previousTimer);
    const label = originalLabel || button.dataset.copyOriginalLabel || button.textContent;
    button.dataset.copyOriginalLabel = label;
    button.textContent = "복사됨 ✓";
    button.setAttribute("aria-label", `${label}: 복사 완료`);
    const timer = window.setTimeout(() => {
      button.textContent = label;
      button.setAttribute("aria-label", label);
      copyTimers.delete(button);
    }, 2400);
    copyTimers.set(button, timer);
  }

  function showCopyStatus(status, message) {
    if (!status) return;
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.textContent = `✓ ${message}`;
  }

  async function copyValue(text, status, success, button = null) {
    if (!String(text || "").trim()) {
      if (status) status.textContent = "원래 요청을 먼저 입력해 주세요.";
      return false;
    }
    try {
      await navigator.clipboard.writeText(text);
      showCopyStatus(status, success);
      showCopied(button, button?.textContent);
      return true;
    } catch (_error) {
      if (status) {
        status.textContent = "자동 복사에 실패했습니다. 미리보기 내용을 직접 선택해 복사해 주세요.";
      }
      return false;
    }
  }

  function openChatGpt(status) {
    const opened = window.open(chatGptNewChatUrl, "_blank", "noopener,noreferrer");
    if (!opened && status) {
      status.textContent = "팝업이 차단되었습니다. 브라우저 주소창의 팝업 허용을 눌러 주세요.";
      return false;
    }
    return true;
  }

  function removeCodexApplyButtons() {
    document.querySelectorAll("#manual-panel button").forEach((button) => {
      if (button.textContent.includes("다음 Codex 요청")) button.hidden = true;
    });
  }

  function renderCopyOnlyActions(promptText) {
    document.querySelector("#prompt-result-actions")?.remove();
    const completed = document.querySelector("#completed-result");
    if (!completed || !promptText) return;

    const actions = document.createElement("div");
    actions.id = "prompt-result-actions";
    actions.className = "request-actions renderer-actions";

    const status = document.createElement("span");
    status.className = "renderer-proof";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.textContent = "AI 최종 편집 결과 검증 완료 · Codex 0회";

    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "secondary-button";
    copyButton.textContent = "최종 프롬프트 복사";
    copyButton.addEventListener("click", async () => {
      await copyValue(
        promptText,
        status,
        "최종 프롬프트를 클립보드에 복사했습니다.",
        copyButton,
      );
    });

    actions.append(status, copyButton);
    completed.appendChild(actions);
  }

  function buildFlowGuide() {
    const existing = document.querySelector("#integrated-flow-guide");
    if (existing) return existing;

    const guide = document.createElement("div");
    guide.id = "integrated-flow-guide";
    guide.className = "integrated-flow-guide";
    [
      ["1", "원래 요청 적기"],
      ["2", "설계·최종 편집 지시문 복사"],
      ["3", "ChatGPT 답변 붙이기"],
      ["4", "최종 프롬프트 꺼내기"],
    ].forEach(([number, text]) => {
      const item = document.createElement("div");
      item.className = "integrated-flow-item";
      item.innerHTML = `<strong>${number}</strong><span>${text}</span>`;
      guide.appendChild(item);
    });
    intro?.after(guide);
    return guide;
  }

  function buildInstructionPreview() {
    const existing = document.querySelector("#integrated-instruction-step");
    if (existing) {
      return {
        section: existing,
        preview: existing.querySelector("#integrated-instruction-preview"),
        copyButton: existing.querySelector("#copy-integrated-instruction"),
        openButton: existing.querySelector("#copy-and-open-chatgpt"),
        status: existing.querySelector(".instruction-copy-status"),
      };
    }

    const section = document.createElement("section");
    section.id = "integrated-instruction-step";
    section.className = "integrated-instruction-step";

    const heading = document.createElement("div");
    heading.className = "manual-step-heading";
    heading.innerHTML = `
      <span class="step-label">02 · 설계와 최종 편집</span>
      <h3>통합 AI 지시문</h3>
      <p>ChatGPT가 Goal Ledger와 Brief를 만든 뒤, 메타 정보와 중복을 걷어내고 실제 실행용 final_prompt까지 직접 편집합니다.</p>`;

    const preview = document.createElement("textarea");
    preview.id = "integrated-instruction-preview";
    preview.rows = 10;
    preview.readOnly = true;
    preview.setAttribute("aria-label", "설계와 최종 편집을 한 번에 수행하는 통합 지시문 미리보기");

    const actionRow = document.createElement("div");
    actionRow.className = "request-actions manual-step-actions";
    const status = document.createElement("span");
    status.className = "renderer-proof instruction-copy-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.textContent = "원래 요청을 적으면 통합 지시문이 자동으로 완성됩니다.";

    const buttonBox = document.createElement("div");
    buttonBox.className = "approval-actions";

    const copyButton = document.createElement("button");
    copyButton.id = "copy-integrated-instruction";
    copyButton.type = "button";
    copyButton.className = "secondary-button";
    copyButton.textContent = "2. 통합 지시문 복사";

    const openButton = document.createElement("button");
    openButton.id = "copy-and-open-chatgpt";
    openButton.type = "button";
    openButton.className = "secondary-button";
    openButton.textContent = "복사하고 ChatGPT 새 채팅 열기";

    buttonBox.append(copyButton, openButton);
    actionRow.append(status, buttonBox);

    section.append(heading, preview, actionRow);
    const requestLabel = closestLabel(requestField);
    requestLabel?.after(section);
    return { section, preview, copyButton, openButton, status };
  }

  const actions = form.querySelector(".renderer-actions");
  const proof = actions?.querySelector(".renderer-proof");
  if (proof) {
    proof.setAttribute("role", "status");
    proof.setAttribute("aria-live", "polite");
  }
  const instructionUi = buildInstructionPreview();
  buildFlowGuide();

  function refreshInstructionPreview() {
    const request = requestField.value.trim();
    instructionUi.preview.value = request ? integratedInstruction(request) : "";
    if (!request) {
      instructionUi.preview.placeholder = "1단계에 원래 요청을 적으면 설계와 최종 편집 지시문이 여기에 나타납니다.";
      instructionUi.status.textContent = "원래 요청을 적으면 통합 지시문이 자동으로 완성됩니다.";
    } else {
      instructionUi.status.textContent = "한 번의 ChatGPT 응답에서 설계와 최종 프롬프트 편집까지 수행합니다.";
    }
  }

  function configureIntegratedUi() {
    const option = integratedMode.closest(".mode-option");
    if (option) {
      option.querySelector("strong").textContent = "통합 AI 1회 · 최종 편집 포함";
      option.querySelector("small").textContent =
        "ChatGPT가 설계와 최종 프롬프트 편집을 한 번에 수행합니다. Codex는 쓰지 않습니다.";
    }

    if (intro) {
      intro.querySelector("strong").textContent = "이번 통합안은 AI가 마지막 편집까지 합니다.";
      intro.querySelector("p").textContent =
        "Goal Ledger와 Brief를 만든 뒤 필드를 그대로 붙이지 않고, 메타 정보와 중복을 제거한 실제 실행용 final_prompt를 같은 응답에서 작성합니다.";
    }

    const requestLabel = closestLabel(requestField);
    if (requestLabel) requestLabel.querySelector("span").textContent = "1. 원래 요청";
    requestField.rows = 6;
    requestField.placeholder =
      "예: 첨부한 여러 시간대 차트를 보고 지금 진입할지, 손절과 분할익절을 어떻게 할지 판단하는 프롬프트를 만들어 줘.";

    const designLabel = closestLabel(designField);
    if (designLabel) {
      designLabel.hidden = false;
      designLabel.classList.add("integrated-json-label");
      designLabel.querySelector("span").textContent = "3. ChatGPT 답변 전체 붙여넣기";
      let help = designLabel.querySelector(".integrated-field-help");
      if (!help) {
        help = document.createElement("small");
        help.className = "integrated-field-help";
        designLabel.insertBefore(help, designField);
      }
      help.textContent = "응답에는 goal_ledger, prompt_build_brief, final_prompt가 함께 들어 있어야 합니다. 받은 JSON 전체를 그대로 붙이세요.";
    }
    designField.rows = 12;
    designField.placeholder = "ChatGPT가 반환한 JSON 전체를 붙여 넣으세요. final_prompt까지 포함되어 있어야 합니다. ```json 코드블록도 허용됩니다.";
    designField.removeAttribute("required");

    [constraintsField, completionField].forEach((field) => {
      const label = closestLabel(field);
      if (label) label.hidden = true;
      field?.removeAttribute("required");
    });
    if (optional) optional.hidden = true;

    if (proof) proof.textContent = "붙여 넣은 설계 구조를 검증하고 AI가 작성한 final_prompt만 꺼냅니다.";
    submitButton.querySelector("span:first-child").textContent = "4. 검증하고 최종 프롬프트 꺼내기";
    form.querySelector(".safety-note").textContent =
      "서버는 Codex나 API를 호출하지 않고 문장을 다시 조립하지도 않습니다. 붙여 넣은 JSON을 검사한 뒤 ChatGPT가 최종 편집한 final_prompt를 그대로 사용합니다.";

    const footer = document.querySelector("footer span:last-child");
    if (footer) footer.textContent = "통합 비교: ChatGPT 설계+최종 편집 1회 · Codex 호출 없음";
    removeCodexApplyButtons();
    refreshInstructionPreview();
  }

  function configureModeNote() {
    const selected = document.querySelector('input[name="engine-mode"]:checked')?.value;
    if (selected === "integrated") {
      sectionNote.textContent = "원래 요청 → ChatGPT 설계·최종 편집 1회 → JSON 검증 → final_prompt 추출 순서입니다.";
    } else if (selected === "manual") {
      sectionNote.textContent = "예전 4단계 결과를 만든 뒤 두 최종 결과를 함께 복사합니다.";
    }
    removeCodexApplyButtons();
  }

  instructionUi.copyButton?.addEventListener("click", async () => {
    await copyValue(
      instructionUi.preview.value,
      instructionUi.status,
      "통합 지시문을 복사했습니다. ChatGPT에 붙여넣고 답변 전체를 3단계에 붙이세요.",
      instructionUi.copyButton,
    );
  });

  instructionUi.openButton?.addEventListener("click", async () => {
    const copied = await copyValue(
      instructionUi.preview.value,
      instructionUi.status,
      "복사했습니다. 열린 ChatGPT 새 채팅에서 Ctrl+V로 붙여넣으세요.",
      instructionUi.openButton,
    );
    if (copied) openChatGpt(instructionUi.status);
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || !button.textContent.includes("복사")) return;
    if (button.id === "copy-integrated-instruction" || button.id === "copy-and-open-chatgpt") return;
    const originalLabel = button.textContent;
    window.setTimeout(() => {
      const status = nearbyStatus(button);
      const message = status?.textContent || "";
      const succeeded = message.includes("복사") &&
        !message.includes("실패") &&
        !message.includes("먼저") &&
        !message.includes("준비");
      if (!succeeded) return;
      showCopied(button, originalLabel);
      if (status && !message.startsWith("✓")) showCopyStatus(status, message);
    }, 120);
  });

  requestField.addEventListener("input", refreshInstructionPreview);
  designField.addEventListener("input", () => {
    if (designField.value.trim()) {
      if (proof) proof.textContent = "답변이 붙었습니다. 이제 구조를 검증하고 final_prompt를 꺼내세요.";
    }
  });

  form.addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const request = requestField.value.trim();
      const integratedDesign = designField.value.trim();
      if (!request) {
        if (proof) proof.textContent = "1단계에 원래 요청을 먼저 입력해 주세요.";
        requestField.focus();
        return;
      }
      if (!integratedDesign) {
        if (proof) proof.textContent = "2단계 지시문을 ChatGPT에 보내고, 받은 답변을 3단계에 붙여 넣어 주세요.";
        designField.focus();
        return;
      }

      document.querySelector("#prompt-result-actions")?.remove();
      submitButton.disabled = true;
      setResultState("running");
      elements.runningTitle.textContent = "통합 JSON을 검증하고 있습니다.";
      elements.runningDetail.textContent = "Codex 호출이나 로컬 재조립 없이 설계 조건과 final_prompt를 확인합니다.";
      try {
        const data = await requestJson("/api/design-prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request, integrated_design: integratedDesign }),
        });
        window.localStorage.setItem(latestPromptKey, data.result_markdown);
        window.localStorage.setItem(latestRequestKey, request);
        const integratedCompare = document.querySelector("#manual-integrated-result");
        if (integratedCompare) integratedCompare.value = data.result_markdown;
        const manualRequest = document.querySelector("#manual-request");
        if (manualRequest && !manualRequest.value.trim()) manualRequest.value = request;
        showCompleted(data);
        renderCopyOnlyActions(data.result_markdown);
      } catch (error) {
        showError(error.message);
      } finally {
        submitButton.disabled = false;
      }
    },
    true,
  );

  document.querySelectorAll('input[name="engine-mode"]').forEach((mode) => {
    mode.addEventListener("change", () => {
      configureIntegratedUi();
      configureModeNote();
    });
  });

  configureIntegratedUi();
  const saved = window.localStorage.getItem(engineStorageKey);
  if (!saved || saved === "codex" || saved === "deterministic") {
    integratedMode.checked = true;
    window.localStorage.setItem(engineStorageKey, "integrated");
    integratedMode.dispatchEvent(new Event("change", { bubbles: true }));
  } else {
    configureModeNote();
  }
})();
