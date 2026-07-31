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
  const blindMapKey = "psos-blind-comparison-map";
  const chatGptNewChatUrl = "https://chatgpt.com/";
  const copyTimers = new WeakMap();

  if (!integratedMode || !form || !requestField || !designField || !submitButton) return;

  function closestLabel(field) {
    return field?.closest(".field-label") || null;
  }

  function integratedInstruction(request) {
    return `당신은 Personal Problem-Solving OS의 통합 프롬프트 설계기다.

사용자의 요청을 한 번만 분석해 다음 세 논리 단계를 내부에서 순서대로 수행한다.

1. 재사용 가능한 프롬프트 제작에 필요한 Goal Ledger를 작성한다.
2. 그 Goal Ledger를 기준으로 Prompt Build Brief를 작성한다.
3. Goal Ledger와 Brief를 바탕으로 다른 AI가 바로 실행할 최종 프롬프트를 작성한다.

설명이나 마크다운 코드블록 없이 JSON 객체 하나만 출력한다.

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

[최종 프롬프트 작성 규칙]
1. final_prompt는 복사해 바로 실행할 완성된 프롬프트다.
2. Goal Ledger, Prompt Build Brief, PSOS, 설계 계약, 검증된 상위 맥락 등 제작 과정의 명칭이나 설명을 넣지 않는다.
3. Brief의 목표·도메인 절차·고정 조건·예외·제외 범위·출력 계약을 실제 실행 지침으로 통합한다.
4. 같은 뜻이 여러 필드에 있으면 한 번만 남기고, 중요도가 낮은 범용 원칙은 실제 결과를 바꾸는 경우에만 포함한다.
5. 입력 → 판단·처리 절차 → 제한·예외 → 출력 형식이 자연스럽게 이어지도록 편집한다.
6. 최종 프롬프트가 프롬프트를 다시 만들라고 요구하지 않게 한다.
7. 내부 검토나 작성 과정을 설명하지 말고 최종 지침만 쓴다.
8. 사용자가 요구하지 않았고 근거도 정의되지 않은 신뢰도 등급·점수·백분율을 출력 형식에 추가하지 않는다.
9. 신규 진입 판단과 보유 포지션 관리처럼 서로 다른 판단 축을 하나의 선택지 목록에 섞지 말고 필요한 경우 각각 분리한다.
10. 누락된 기간·성향·기준을 처리할 때 임의의 고정값을 넣지 않는다. 제공된 입력 구성을 바탕으로 추정하고 추정임을 밝히거나, 결과가 크게 달라질 때만 질문한다.
11. final_prompt는 JSON 문자열이어야 하므로 실제 줄바꿈은 \\n으로 이스케이프한다.

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
  "final_prompt": "# 역할과 목표\\n\\n..."
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
      if (status) status.textContent = "먼저 필요한 내용을 입력해 주세요.";
      return false;
    }
    try {
      await navigator.clipboard.writeText(text);
      showCopyStatus(status, success);
      showCopied(button, button?.textContent);
      return true;
    } catch (_error) {
      if (status) {
        status.textContent = "자동 복사에 실패했습니다. 내용을 직접 선택해 복사해 주세요.";
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
    status.textContent = "AI 작성 최종 프롬프트 검증·추출 완료";

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
      ["2", "통합 제작 지시문 복사"],
      ["3", "ChatGPT 결과 붙이기"],
      ["4", "최종 프롬프트 추출"],
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
      <span class="step-label">02 · 통합 제작</span>
      <h3>설계와 최종 작성을 한 번에 하는 지시문</h3>
      <p>이 지시문이 네 요청을 분석해 Goal Ledger와 Brief를 만든 뒤, 중복과 메타 정보를 버린 최종 프롬프트까지 직접 작성합니다.</p>`;

    const preview = document.createElement("textarea");
    preview.id = "integrated-instruction-preview";
    preview.rows = 10;
    preview.readOnly = true;
    preview.setAttribute("aria-label", "설계와 최종 작성을 한 번에 하는 지시문 미리보기");

    const actionRow = document.createElement("div");
    actionRow.className = "request-actions manual-step-actions";
    const status = document.createElement("span");
    status.className = "renderer-proof instruction-copy-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.textContent = "원래 요청을 적으면 통합 제작 지시문이 자동으로 완성됩니다.";

    const buttonBox = document.createElement("div");
    buttonBox.className = "approval-actions";

    const copyButton = document.createElement("button");
    copyButton.id = "copy-integrated-instruction";
    copyButton.type = "button";
    copyButton.className = "secondary-button";
    copyButton.textContent = "2. 통합 제작 지시문 복사";

    const openButton = document.createElement("button");
    openButton.id = "copy-and-open-chatgpt";
    openButton.type = "button";
    openButton.className = "secondary-button";
    openButton.textContent = "복사하고 ChatGPT 새 채팅 열기";

    buttonBox.append(copyButton, openButton);
    actionRow.append(status, buttonBox);
    section.append(heading, preview, actionRow);
    closestLabel(requestField)?.after(section);
    return { section, preview, copyButton, openButton, status };
  }

  function randomBlindMap() {
    let integratedFirst;
    if (window.crypto?.getRandomValues) {
      const value = new Uint32Array(1);
      window.crypto.getRandomValues(value);
      integratedFirst = value[0] % 2 === 0;
    } else {
      integratedFirst = Math.random() < 0.5;
    }
    const map = integratedFirst
      ? { A: "integrated", B: "manual" }
      : { A: "manual", B: "integrated" };
    window.localStorage.setItem(blindMapKey, JSON.stringify(map));
    return map;
  }

  function loadBlindMap() {
    try {
      const map = JSON.parse(window.localStorage.getItem(blindMapKey) || "null");
      if (map?.A && map?.B && map.A !== map.B) return map;
    } catch (_error) {
      // Fall through and create a fresh map.
    }
    return randomBlindMap();
  }

  function installBlindComparisonControls() {
    const compare = document.querySelector("#manual-panel .manual-compare");
    if (!compare || compare.querySelector("#copy-blind-a")) return;
    const actions = compare.querySelector(".manual-step-actions");
    const status = actions?.querySelector(".renderer-proof");
    const integrated = compare.querySelector("#manual-integrated-result");
    const manual = compare.querySelector("#manual-compare-final");
    if (!actions || !status || !integrated || !manual) return;

    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const buttonBox = document.createElement("div");
    buttonBox.className = "approval-actions blind-compare-actions";
    actions.querySelectorAll("button").forEach((button) => buttonBox.appendChild(button));

    const copyA = document.createElement("button");
    copyA.id = "copy-blind-a";
    copyA.type = "button";
    copyA.className = "secondary-button";
    copyA.textContent = "블라인드 A 복사";

    const copyB = document.createElement("button");
    copyB.id = "copy-blind-b";
    copyB.type = "button";
    copyB.className = "secondary-button";
    copyB.textContent = "블라인드 B 복사";

    const reshuffle = document.createElement("button");
    reshuffle.id = "reshuffle-blind-map";
    reshuffle.type = "button";
    reshuffle.className = "secondary-button";
    reshuffle.textContent = "A/B 다시 섞기";

    const reveal = document.createElement("button");
    reveal.id = "reveal-blind-map";
    reveal.type = "button";
    reveal.className = "secondary-button";
    reveal.textContent = "A/B 정답 확인";

    function ready() {
      if (!integrated.value.trim() || !manual.value.trim()) {
        status.textContent = "통합 AI 결과와 수동 최종 결과를 모두 준비해 주세요.";
        return false;
      }
      return true;
    }

    function promptFor(label) {
      const map = loadBlindMap();
      return map[label] === "integrated" ? integrated.value : manual.value;
    }

    copyA.addEventListener("click", async () => {
      if (!ready()) return;
      await copyValue(
        promptFor("A"),
        status,
        "블라인드 A를 복사했습니다. 같은 차트와 입력으로 새 채팅에서 실행하세요.",
        copyA,
      );
    });

    copyB.addEventListener("click", async () => {
      if (!ready()) return;
      await copyValue(
        promptFor("B"),
        status,
        "블라인드 B를 복사했습니다. A와 동일한 차트와 입력으로 새 채팅에서 실행하세요.",
        copyB,
      );
    });

    reshuffle.addEventListener("click", () => {
      randomBlindMap();
      status.textContent = "A/B 순서를 새로 무작위 배정했습니다. 두 결과를 실행하기 전에는 다시 섞지 마세요.";
    });

    reveal.addEventListener("click", () => {
      const map = loadBlindMap();
      const name = (value) => value === "integrated" ? "통합 AI 1회" : "수동 PSOS 4단계";
      status.textContent = `정답: A = ${name(map.A)} · B = ${name(map.B)}`;
    });

    buttonBox.append(copyA, copyB, reshuffle, reveal);
    actions.appendChild(buttonBox);
    const headingNote = compare.querySelector(".manual-step-heading p");
    if (headingNote) {
      headingNote.textContent = "이름이 보이는 비교용 복사와, 동일한 차트로 실행할 무작위 A/B 복사를 함께 제공합니다.";
    }
  }

  const actions = form.querySelector(".renderer-actions");
  const proof = actions?.querySelector(".renderer-proof");
  if (proof) {
    proof.setAttribute("role", "status");
    proof.setAttribute("aria-live", "polite");
  }
  const instructionUi = buildInstructionPreview();
  buildFlowGuide();
  installBlindComparisonControls();

  function refreshInstructionPreview() {
    const request = requestField.value.trim();
    instructionUi.preview.value = request ? integratedInstruction(request) : "";
    if (!request) {
      instructionUi.preview.placeholder = "1단계에 원래 요청을 적으면 통합 제작 지시문을 확인할 수 있습니다.";
      instructionUi.status.textContent = "원래 요청을 적으면 통합 제작 지시문이 자동으로 완성됩니다.";
    } else {
      instructionUi.status.textContent = "한 번의 AI 응답에서 설계와 최종 편집까지 수행하도록 지시합니다.";
    }
  }

  function configureIntegratedUi() {
    const option = integratedMode.closest(".mode-option");
    if (option) {
      option.querySelector("strong").textContent = "통합 AI 1회 · 최종 편집 포함";
      option.querySelector("small").textContent =
        "AI가 설계와 최종 프롬프트 작성을 한 번에 수행합니다. Codex는 사용하지 않습니다.";
    }

    if (intro) {
      intro.querySelector("strong").textContent = "이번 통합안은 AI가 최종 프롬프트까지 직접 씁니다.";
      intro.querySelector("p").textContent =
        "Goal Ledger와 Brief를 기계적으로 이어 붙이지 않습니다. ChatGPT가 중복과 제작 흔적을 제거해 최종 실행용 프롬프트까지 한 번에 반환합니다.";
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
      help.textContent = "2단계 지시문을 ChatGPT 새 채팅에 보내고, final_prompt가 포함된 JSON 답변 전체를 그대로 붙여 넣으세요.";
    }
    designField.rows = 12;
    designField.placeholder = "ChatGPT가 반환한 goal_ledger, prompt_build_brief, final_prompt 전체 JSON을 붙여 넣으세요. ```json 코드블록도 허용됩니다.";
    designField.removeAttribute("required");

    [constraintsField, completionField].forEach((field) => {
      const label = closestLabel(field);
      if (label) label.hidden = true;
      field?.removeAttribute("required");
    });
    if (optional) optional.hidden = true;

    if (proof) proof.textContent = "붙여 넣은 설계 구조와 final_prompt를 검증한 뒤 AI 작성본을 추출합니다.";
    submitButton.querySelector("span:first-child").textContent = "4. 최종 프롬프트 추출";
    form.querySelector(".safety-note").textContent =
      "서버는 Codex나 API를 호출하지 않습니다. ChatGPT가 같은 응답에서 직접 작성한 final_prompt를 검증하고 그대로 보여 줍니다.";

    const footer = document.querySelector("footer span:last-child");
    if (footer) footer.textContent = "통합 비교: ChatGPT 왕복 1회 · AI 최종 편집 · Codex 호출 없음";
    removeCodexApplyButtons();
    refreshInstructionPreview();
    installBlindComparisonControls();
  }

  function configureModeNote() {
    const selected = document.querySelector('input[name="engine-mode"]:checked')?.value;
    if (selected === "integrated") {
      sectionNote.textContent = "원래 요청 → 통합 제작 지시문 → ChatGPT JSON → AI 작성 최종 프롬프트 추출 순서로 진행합니다.";
    } else if (selected === "manual") {
      sectionNote.textContent = "수동 결과를 완성한 뒤 이름 공개 비교 또는 무작위 A/B 실행을 선택합니다.";
    }
    removeCodexApplyButtons();
    installBlindComparisonControls();
  }

  instructionUi.copyButton?.addEventListener("click", async () => {
    await copyValue(
      instructionUi.preview.value,
      instructionUi.status,
      "통합 제작 지시문을 복사했습니다. ChatGPT에 붙여넣고 답변을 3단계에 붙이세요.",
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
    if (["copy-integrated-instruction", "copy-and-open-chatgpt", "copy-blind-a", "copy-blind-b"].includes(button.id)) return;
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
    if (designField.value.trim() && proof) {
      proof.textContent = "답변이 붙었습니다. 이제 final_prompt 추출 버튼을 누르세요.";
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
      elements.runningTitle.textContent = "통합 JSON과 final_prompt를 검증하고 있습니다.";
      elements.runningDetail.textContent = "Codex 호출 없이 설계 구조를 확인하고 AI가 직접 작성한 최종 프롬프트를 추출합니다.";
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
        installBlindComparisonControls();
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
