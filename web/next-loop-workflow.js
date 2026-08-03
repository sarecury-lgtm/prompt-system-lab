(() => {
  if (typeof elements === "undefined" || typeof promptUi === "undefined") return;

  const AUTO_STORAGE_KEY = "psos-auto-workflow";
  const ADVANCED_STORAGE_KEY = "psos-advanced-workflow";
  const engineSelector = document.querySelector(".engine-selector");
  const requestForm = elements.form;
  const nextLoopToggle = document.querySelector("#next-loop-enabled");
  const writeScope = document.querySelector("#write-scope-panel");
  const allowedPaths = document.querySelector("#allowed-paths");
  const sectionHeading = document.querySelector(".workspace > .section-heading");
  if (!engineSelector || !requestForm || !sectionHeading) return;

  let programmaticChange = false;

  const routeCopy = {
    direct: {
      badge: "일반 해결",
      title: "바로 답하고 필요한 근거만 남깁니다.",
      detail: "최신 검색이나 후보 작업대가 필요하지 않은 요청으로 보입니다.",
    },
    research: {
      badge: "최신 조사",
      title: "웹 검색을 켜고 현재 정보를 확인합니다.",
      detail: "가격·뉴스·규정·현재 상태처럼 시점에 따라 달라질 수 있는 요청입니다.",
    },
    candidate: {
      badge: "후보 비교",
      title: "먼저 후보를 보여주고 중간 교정을 받습니다.",
      detail: "추천·구매·비교 요청이라 한 번에 결론내기보다 후보를 압축하는 편이 안전합니다.",
    },
    prompt: {
      badge: "프롬프트 제작",
      title: "통합 AI 1회로 최종 프롬프트를 만듭니다.",
      detail: "Goal Ledger와 Brief를 한 번에 설계하고 로컬에서 최종 조립합니다.",
    },
    write: {
      badge: "파일 변경",
      title: "허용 경로를 확인한 뒤 파일을 직접 수정합니다.",
      detail: "안전을 위해 변경 가능한 파일이나 폴더를 한 번 지정해야 합니다.",
    },
    manual: {
      badge: "수동 선택",
      title: "아래 고급 설정을 그대로 사용합니다.",
      detail: "자동 추천을 끄고 실행 방식과 검색 여부를 직접 정한 상태입니다.",
    },
  };

  function classifyRequest(value) {
    const text = String(value || "").trim();
    if (!text) return "direct";

    const writeTarget = /(코드|파일|폴더|웹페이지|웹사이트|앱|프로젝트|저장소|레포|repository|html|css|javascript|typescript|python|스크립트)/i.test(text);
    const writeAction = /(만들|구현|수정|고쳐|추가|삭제|리팩터|저장|적용|배포|완성)/i.test(text);
    if (writeTarget && writeAction) return "write";

    const promptWord = /(프롬프트|prompt)/i.test(text);
    const promptAction = /(만들|작성|설계|생성|짜|다듬|개선|최적화)/i.test(text);
    if (promptWord && promptAction) return "prompt";

    const explicitChoice = /(추천|후보|골라|고르|구매|살까)/i.test(text);
    const comparison = /비교/i.test(text);
    const choiceSubject = /(제품|상품|식당|숙소|여행지|종목|보험|카드|영화|게임|가전|고기|과일|의자|제습기)/i.test(text);
    const decisionWord = /(가장|1위|최선|실제로|가격|후기|판매|온라인|현재|조건|취향|예산|살 만)/i.test(text);
    if (explicitChoice || (comparison && (choiceSubject || decisionWord))) return "candidate";

    const currentWord = /(최신|오늘|현재|지금|가격|뉴스|법|규정|일정|패치|버전|검색|조사|찾아|확인|검증|판매 중|재고)/i.test(text);
    if (currentWord) return "research";
    return "direct";
  }

  const guide = document.createElement("section");
  guide.id = "workflow-guide";
  guide.className = "workflow-guide";
  guide.innerHTML = `
    <div class="workflow-guide-head">
      <div>
        <span class="workflow-kicker">실행 방식 자동 선택</span>
        <h3 id="workflow-title"></h3>
        <p id="workflow-detail"></p>
      </div>
      <span id="workflow-badge" class="workflow-badge"></span>
    </div>
    <div class="workflow-guide-actions">
      <label class="workflow-auto-toggle">
        <input id="workflow-auto-enabled" type="checkbox">
        <span>
          <strong>요청에 맞춰 자동 선택</strong>
          <small>일반 해결·최신 조사·후보 비교·프롬프트 제작을 자동으로 고릅니다.</small>
        </span>
      </label>
      <button id="workflow-advanced-toggle" type="button" class="secondary-button">고급 설정 보기</button>
    </div>
  `;
  sectionHeading.insertAdjacentElement("afterend", guide);

  const autoToggle = guide.querySelector("#workflow-auto-enabled");
  const advancedButton = guide.querySelector("#workflow-advanced-toggle");
  const titleNode = guide.querySelector("#workflow-title");
  const detailNode = guide.querySelector("#workflow-detail");
  const badgeNode = guide.querySelector("#workflow-badge");

  function autoEnabled() {
    return autoToggle.checked;
  }

  function advancedVisible() {
    return document.body.classList.contains("workflow-show-advanced");
  }

  function setAdvancedVisible(visible) {
    document.body.classList.toggle("workflow-show-advanced", visible);
    advancedButton.textContent = visible ? "고급 설정 숨기기" : "고급 설정 보기";
    window.localStorage.setItem(ADVANCED_STORAGE_KEY, String(visible));
  }

  function renderRoute(route) {
    const copy = routeCopy[route] || routeCopy.direct;
    titleNode.textContent = copy.title;
    detailNode.textContent = copy.detail;
    badgeNode.textContent = copy.badge;
    badgeNode.dataset.route = route;
  }

  function updateRecommendation() {
    if (!autoEnabled()) {
      renderRoute("manual");
      return "manual";
    }
    const route = classifyRequest(elements.request.value);
    renderRoute(route);
    return route;
  }

  function setAutoEnabled(enabled, { preserveAdvanced = false } = {}) {
    autoToggle.checked = Boolean(enabled);
    document.body.classList.toggle("workflow-auto", Boolean(enabled));
    window.localStorage.setItem(AUTO_STORAGE_KEY, String(Boolean(enabled)));
    if (enabled) selectEngine("codex");
    if (!enabled && !preserveAdvanced) setAdvancedVisible(true);
    updateRecommendation();
  }

  function checkRadio(radios, value) {
    radios.forEach((radio) => {
      radio.checked = radio.value === value;
    });
  }

  function dispatchChange(node) {
    node?.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function runProgrammatically(callback) {
    const previous = programmaticChange;
    programmaticChange = true;
    try {
      callback();
    } finally {
      programmaticChange = previous;
    }
  }

  function selectEngine(value) {
    runProgrammatically(() => {
      checkRadio(promptUi.modes, value);
      updateEngineMode();
    });
  }

  function prepareCodexRoute(route) {
    runProgrammatically(() => {
      selectEngine("codex");
      if (nextLoopToggle) {
        nextLoopToggle.checked = route === "candidate";
        dispatchChange(nextLoopToggle);
      }
      checkRadio(elements.modes, route === "write" ? "write" : "read");
      elements.search.checked = ["research", "candidate"].includes(route);
      updateMode();
    });
  }

  function renameOptions() {
    const codexOption = engineSelector.querySelector('input[value="codex"]')?.closest(".mode-option");
    const integratedOption = engineSelector.querySelector('input[value="integrated"]')?.closest(".mode-option");
    const manualOption = engineSelector.querySelector('input[value="manual"]')?.closest(".mode-option");
    if (codexOption) {
      codexOption.querySelector("strong").textContent = "문제 해결";
      codexOption.querySelector("small").textContent = "일반 답변·최신 조사·후보 비교·파일 작업을 수행합니다.";
    }
    if (integratedOption) {
      integratedOption.querySelector("strong").textContent = "프롬프트 만들기";
      integratedOption.querySelector("small").textContent = "AI 한 번으로 구조를 설계하고 최종 프롬프트를 조립합니다.";
    }
    if (manualOption) {
      manualOption.querySelector("strong").textContent = "프롬프트 실험 · 수동 4단계";
      manualOption.querySelector("small").textContent = "비교·진단용입니다. 세 번의 AI 결과를 직접 옮겨 붙입니다.";
    }

    const readOption = requestForm.querySelector('input[name="work-mode"][value="read"]')?.closest(".mode-option");
    const writeOption = requestForm.querySelector('input[name="work-mode"][value="write"]')?.closest(".mode-option");
    if (readOption) {
      readOption.querySelector("strong").textContent = "답변·조사";
      readOption.querySelector("small").textContent = "파일은 읽을 수 있지만 변경하지 않습니다.";
    }
    if (writeOption) {
      writeOption.querySelector("strong").textContent = "파일 직접 수정";
      writeOption.querySelector("small").textContent = "허용 경로를 확인한 뒤 실제 파일을 변경합니다.";
    }

    const nextLoopText = document.querySelector(".next-loop-control span");
    if (nextLoopText) {
      nextLoopText.querySelector("strong").textContent = "후보를 먼저 보여주고 중간 수정";
      nextLoopText.querySelector("small").textContent = "추천·구매·선택 요청에서 후보를 본 뒤 조건을 바꿉니다.";
    }
    const searchText = elements.search.closest("label")?.querySelector("span");
    if (searchText) searchText.textContent = "최신 정보 검색 허용";
  }

  function improveManualPanel() {
    const panel = document.querySelector("#manual-panel");
    if (!panel || panel.querySelector("#manual-progress")) return;
    panel.classList.add("manual-diagnostic-panel");
    const intro = panel.querySelector(".renderer-intro");
    if (intro) {
      intro.querySelector("strong").textContent = "비교·진단용 수동 워크플로";
      intro.querySelector("p").textContent =
        "평소 사용용이 아니라 통합 방식과 단계별 결과를 비교하거나, 어느 단계에서 품질이 무너지는지 확인할 때 씁니다.";
    }

    const progress = document.createElement("div");
    progress.id = "manual-progress";
    progress.className = "manual-progress";
    progress.innerHTML = `
      <div><strong>진행도</strong><span id="manual-progress-label">0 / 4</span></div>
      <div class="manual-progress-track"><span></span></div>
      <div class="manual-progress-actions">
        <button id="manual-copy-state" type="button" class="secondary-button">현재 상태 복사</button>
        <button id="manual-reset-state" type="button" class="secondary-button">수동 작업 초기화</button>
      </div>
    `;
    intro?.insertAdjacentElement("afterend", progress);

    const fields = [
      document.querySelector("#manual-request"),
      document.querySelector("#manual-ledger"),
      document.querySelector("#manual-brief"),
      document.querySelector("#manual-final"),
    ].filter(Boolean);
    const label = progress.querySelector("#manual-progress-label");
    const bar = progress.querySelector(".manual-progress-track span");

    function refreshProgress() {
      const completed = fields.filter((field) => field.value.trim()).length;
      label.textContent = `${completed} / 4`;
      bar.style.width = `${completed * 25}%`;
      panel.querySelectorAll(".manual-step").forEach((step, index) => {
        step.classList.toggle("manual-current-step", index === completed && completed < 4);
        step.classList.toggle("manual-completed-step", index < completed);
      });
    }
    fields.forEach((field) => field.addEventListener("input", refreshProgress));

    progress.querySelector("#manual-copy-state").addEventListener("click", () => {
      const text = fields
        .map((field, index) => `# ${index + 1}단계\n\n${field.value.trim() || "(비어 있음)"}`)
        .join("\n\n---\n\n");
      const status = panel.querySelector(".renderer-proof") || label;
      copyText(text, status, "수동 4단계 상태를 복사했습니다.");
    });
    progress.querySelector("#manual-reset-state").addEventListener("click", () => {
      fields.forEach((field) => {
        field.value = "";
        dispatchChange(field);
        field.dispatchEvent(new Event("input", { bubbles: true }));
      });
      window.localStorage.removeItem("psos-manual-workflow-state");
      refreshProgress();
      fields[0]?.focus();
    });
    refreshProgress();
  }

  function describeWriteBlocker() {
    renderRoute("write");
    detailNode.textContent = "파일을 바꿀 범위를 모르므로 고급 설정에서 허용 경로를 한 줄에 하나 입력해 주세요.";
    setAdvancedVisible(true);
    writeScope.hidden = false;
    allowedPaths?.focus();
  }

  async function runPromptFromMain(request) {
    document.querySelector("#prompt-result-actions")?.remove();
    elements.submit.disabled = true;
    setResultState("running");
    elements.runningTitle.textContent = "프롬프트 구조를 한 번에 설계하고 있습니다.";
    elements.runningDetail.textContent = "Goal Ledger와 Brief를 만든 뒤 로컬에서 최종 프롬프트를 조립합니다.";
    try {
      const data = await requestJson("/api/design-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request }),
      });
      window.localStorage.setItem("psos-latest-integrated-prompt", data.result_markdown);
      window.localStorage.setItem("psos-latest-integrated-request", request);
      const integratedCompare = document.querySelector("#manual-integrated-result");
      if (integratedCompare) integratedCompare.value = data.result_markdown;
      const manualRequest = document.querySelector("#manual-request");
      if (manualRequest && !manualRequest.value.trim()) manualRequest.value = request;
      showCompleted(data);
      renderPromptResultActions(data.result_markdown, "자동 선택 · 프롬프트 제작 결과");
    } catch (error) {
      showError(error.message);
    } finally {
      elements.submit.disabled = false;
    }
  }

  requestForm.addEventListener(
    "submit",
    (event) => {
      if (!autoEnabled()) return;
      const request = elements.request.value.trim();
      const route = classifyRequest(request);
      renderRoute(route);

      if (route === "prompt") {
        event.preventDefault();
        event.stopImmediatePropagation();
        prepareCodexRoute("direct");
        runPromptFromMain(request);
        return;
      }

      prepareCodexRoute(route);
      if (route === "candidate") {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.queueMicrotask(() => requestForm.requestSubmit());
        return;
      }
      if (route === "write" && !allowedPaths?.value.trim()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        describeWriteBlocker();
      }
    },
    true,
  );

  autoToggle.addEventListener("change", () => {
    setAutoEnabled(autoToggle.checked);
  });
  advancedButton.addEventListener("click", () => {
    setAdvancedVisible(!advancedVisible());
  });
  elements.request.addEventListener("input", updateRecommendation);

  [
    ...promptUi.modes,
    ...elements.modes,
    nextLoopToggle,
    elements.search,
  ]
    .filter(Boolean)
    .forEach((control) => {
      control.addEventListener("change", () => {
        if (!programmaticChange && autoEnabled()) {
          setAutoEnabled(false, { preserveAdvanced: true });
          setAdvancedVisible(true);
        }
      });
    });

  renameOptions();
  improveManualPanel();

  const footerSummary = document.querySelector("footer span:last-child");
  if (footerSummary) {
    footerSummary.textContent = "요청 하나 입력 · 실행 방식 자동 추천 · 필요할 때만 고급 설정";
  }

  const savedAuto = window.localStorage.getItem(AUTO_STORAGE_KEY);
  const savedAdvanced = window.localStorage.getItem(ADVANCED_STORAGE_KEY);
  setAdvancedVisible(savedAdvanced === "true");
  setAutoEnabled(savedAuto !== "false", { preserveAdvanced: true });
  window.PSOSWorkflowRouter = Object.freeze({ classifyRequest });
  updateRecommendation();
})();
