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

  if (!integratedMode || !form || !requestField || !designField || !submitButton) return;

  function closestLabel(field) {
    return field?.closest(".field-label") || null;
  }

  function integratedInstruction(request) {
    return `당신은 Personal Problem-Solving OS의 통합 프롬프트 설계기다.

사용자의 요청을 한 번만 분석해 다음 두 논리 단계를 함께 수행한다.

1. 재사용 가능한 프롬프트 제작에 필요한 Goal Ledger를 작성한다.
2. 그 Goal Ledger를 기준으로 Prompt Build Brief를 작성한다.

이 단계에서는 최종 프롬프트 본문을 작성하지 않는다. 설명이나 마크다운 코드블록 없이 JSON 객체 하나만 출력한다.

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
3. supporting_inputs에는 절차 수행에 필요한 자료, 입력 형태, 분석 요소, 도구만 둔다.
4. fixed_constraints는 Goal Ledger의 fixed_constraints를 문구와 순서까지 정확히 복사한다.
5. output_contract의 첫 항목은 Goal Ledger의 completion_condition과 정확히 같아야 한다.
6. 나머지 output_contract에는 사용자가 실제로 비교·판단·행동하는 데 필요한 산출물만 둔다.
7. defaults_and_exceptions에는 누락 정보 처리처럼 결과가 달라지는 기본값만 둔다.
8. exclusions에는 목표 밖의 작업만 둔다.
9. 같은 의미를 여러 필드에 반복하지 않는다.
10. core_procedure를 “요청 파악 → 작업 수행 → 결과 제시” 같은 범용 절차로 끝내지 않는다.

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
  }
}

[사용자 요청]
${request.trim()}`;
  }

  async function copyValue(text, status, success) {
    if (!String(text || "").trim()) {
      status.textContent = "요청을 먼저 입력해 주세요.";
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = success;
    } catch (_error) {
      status.textContent = "자동 복사에 실패했습니다. 직접 선택해 복사해 주세요.";
    }
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
    status.textContent = "Codex 0회 · 로컬 검증 및 조립 완료";

    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "secondary-button";
    copyButton.textContent = "최종 프롬프트 복사";
    copyButton.addEventListener("click", () => {
      copyValue(promptText, status, "최종 프롬프트를 복사했습니다.");
    });

    actions.append(status, copyButton);
    completed.appendChild(actions);
  }

  const actions = form.querySelector(".renderer-actions");
  const proof = actions?.querySelector(".renderer-proof");
  let copyInstructionButton = document.querySelector("#copy-integrated-instruction");
  if (!copyInstructionButton && actions) {
    copyInstructionButton = document.createElement("button");
    copyInstructionButton.id = "copy-integrated-instruction";
    copyInstructionButton.type = "button";
    copyInstructionButton.className = "secondary-button";
    copyInstructionButton.textContent = "1. 통합 지시문 복사";
    actions.insertBefore(copyInstructionButton, submitButton);
  }

  function configureIntegratedUi() {
    const option = integratedMode.closest(".mode-option");
    if (option) {
      option.querySelector("strong").textContent = "통합 AI 1회 · Codex 없음";
      option.querySelector("small").textContent =
        "지시문을 ChatGPT에 한 번 보내고 JSON을 한 번 붙여 최종 조립합니다.";
    }

    if (intro) {
      intro.querySelector("strong").textContent = "AI 왕복 1회, Codex 호출 0회";
      intro.querySelector("p").textContent =
        "아래 지시문을 복사해 ChatGPT에 한 번 보내고, 받은 JSON을 붙이면 서버가 검증한 뒤 최종 프롬프트를 로컬에서 조립합니다.";
    }

    const requestLabel = closestLabel(requestField);
    if (requestLabel) requestLabel.querySelector("span").textContent = "어떤 프롬프트가 필요한가요?";
    requestField.rows = 6;

    const designLabel = closestLabel(designField);
    if (designLabel) {
      designLabel.hidden = false;
      designLabel.querySelector("span").textContent = "ChatGPT가 반환한 통합 JSON";
    }
    designField.rows = 12;
    designField.placeholder = "복사한 통합 지시문을 ChatGPT에 보내고, 반환된 JSON 전체를 여기에 붙여 넣으세요.";
    designField.removeAttribute("required");

    [constraintsField, completionField].forEach((field) => {
      const label = closestLabel(field);
      if (label) label.hidden = true;
      field?.removeAttribute("required");
    });
    if (optional) optional.hidden = true;

    if (proof) proof.textContent = "외부 AI 왕복 1회 · Codex 0회";
    submitButton.querySelector("span:first-child").textContent = "2. 붙여넣은 JSON으로 조립";
    form.querySelector(".safety-note").textContent =
      "이 모드는 Codex나 API를 호출하지 않습니다. 붙여 넣은 JSON의 구조와 조건 일치만 검사하고 로컬에서 조립합니다.";

    const footer = document.querySelector("footer span:last-child");
    if (footer) footer.textContent = "통합 비교: 외부 AI 왕복 1회 · Codex 호출 없음";
    removeCodexApplyButtons();
  }

  function configureModeNote() {
    const selected = document.querySelector('input[name="engine-mode"]:checked')?.value;
    if (selected === "integrated") {
      sectionNote.textContent = "지시문을 한 번 복사하고 JSON을 한 번 붙여 최종 프롬프트를 조립합니다.";
    } else if (selected === "manual") {
      sectionNote.textContent = "예전 4단계 결과를 만든 뒤 두 최종 결과를 함께 복사합니다.";
    }
    removeCodexApplyButtons();
  }

  copyInstructionButton?.addEventListener("click", () => {
    copyValue(
      integratedInstruction(requestField.value),
      proof,
      "통합 지시문을 복사했습니다. ChatGPT에 보내고 결과 JSON을 아래 칸에 붙이세요.",
    );
  });

  form.addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const request = requestField.value.trim();
      const integratedDesign = designField.value.trim();
      if (!request) {
        requestField.focus();
        return;
      }
      if (!integratedDesign) {
        proof.textContent = "ChatGPT가 반환한 통합 JSON을 먼저 붙여 넣어 주세요.";
        designField.focus();
        return;
      }

      document.querySelector("#prompt-result-actions")?.remove();
      submitButton.disabled = true;
      setResultState("running");
      elements.runningTitle.textContent = "통합 JSON을 검증하고 있습니다.";
      elements.runningDetail.textContent = "Codex 호출 없이 Goal Ledger와 Brief의 조건을 확인한 뒤 로컬에서 조립합니다.";
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
