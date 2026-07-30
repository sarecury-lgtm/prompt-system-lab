const $ = (selector) => document.querySelector(selector);

const startPanel = $("#start-panel");
const handoffPanel = $("#handoff-panel");
const resultPanel = $("#result-panel");
const startButton = $("#start");
const submitButton = $("#submit");
const reviseButton = $("#revise");
const copyPromptButton = $("#copy-prompt");
const openChatGPTButton = $("#open-chatgpt");
const copyResultButton = $("#copy-result");
const comparePromptButton = $("#compare-prompt");
const backToParentButton = $("#back-to-parent");
const showRevisionButton = $("#show-revision");
const statusText = $("#status");
let currentRunId = null;
let currentSession = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body;
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.dataset.label ||= button.textContent;
  button.textContent = busy ? "처리 중…" : button.dataset.label;
}

function setTemporaryLabel(button, label, duration = 1800) {
  const original = button.dataset.label || button.textContent;
  button.textContent = label;
  window.setTimeout(() => {
    button.textContent = original;
  }, duration);
}

async function copyText(value, fallbackElement = null) {
  const text = typeof value === "string" ? value : "";
  if (!text.trim()) throw new Error("복사할 내용이 없습니다.");
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch (_error) {
    const element = fallbackElement || document.createElement("textarea");
    const temporary = !fallbackElement;
    if (temporary) {
      element.value = text;
      element.setAttribute("readonly", "");
      element.style.position = "fixed";
      element.style.opacity = "0";
      document.body.appendChild(element);
    }
    element.focus();
    element.select();
    const copied = document.execCommand("copy");
    if (temporary) element.remove();
    if (!copied) throw new Error("클립보드에 복사하지 못했습니다.");
  }
}

function researchModeLabel(mode) {
  return {
    none: "검색 없음",
    standard: "일반 조사",
    deep: "심층 조사",
  }[mode] || mode;
}

function ablationPresentation(session) {
  const views = {
    ablation_without_raw_request: {
      step: "비교 1/4",
      title: "원문 중복 제거 방식 만들기",
      detail: "Goal Ledger와 Compiler baseline은 유지하고, 따로 반복된 사용자 원문만 뺀 결과를 만듭니다.",
      copyLabel: "1. 비교 후보 A 지시문 복사",
    },
    ablation_compact_ledger: {
      step: "비교 2/4",
      title: "Goal Ledger 축약 방식 만들기",
      detail: "목표·고정 조건·완료 조건만 남긴 계약과 Compiler baseline으로 결과를 만듭니다.",
      copyLabel: "1. 비교 후보 B 지시문 복사",
    },
    ablation_single_build_brief: {
      step: "비교 3/4",
      title: "단일 Build Brief 방식 만들기",
      detail: "중복된 입력 표면을 하나의 brief로 합쳐 핵심 절차 중심의 결과를 만듭니다.",
      copyLabel: "1. 비교 후보 C 지시문 복사",
    },
    ablation_assessment: {
      step: "비교 4/4",
      title: "후보 이름을 가리고 평가하기",
      detail: "현재 방식과 세 변형을 A~D로 가린 채 조건 보존·절차·반복·재사용성을 비교합니다.",
      copyLabel: "1. 블라인드 평가 지시문 복사",
    },
  };
  const current = views[session.phase];
  if (!current) throw new Error(`알 수 없는 비교 단계입니다: ${session.phase}`);
  const isAssessment = session.phase === "ablation_assessment";
  return {
    ...current,
    badge: "일반 ChatGPT · 새 채팅",
    badgeKind: "normal",
    action: "현재 지시문을 복사한 뒤 반드시 새 ChatGPT 채팅을 열어 보내세요. 받은 JSON 전체를 아래 칸에 붙입니다.",
    note: isAssessment
      ? "후보의 내부 이름은 지시문에 포함되지 않습니다. 짧다는 이유만으로 고르지 말고 조건 보존과 실제 작동 구조를 함께 평가합니다."
      : "이전 후보의 답변이 다음 후보에 영향을 주지 않도록 같은 대화방을 이어 쓰지 않습니다.",
    responseLabel: isAssessment
      ? "블라인드 평가 JSON 전체 붙여넣기"
      : "생성된 프롬프트 JSON 전체 붙여넣기",
    responseHelp: "ChatGPT가 반환한 JSON 전체를 수정하지 말고 그대로 붙이세요.",
    responsePlaceholder: "ChatGPT 답변 JSON 전체를 여기에 붙여넣으세요.",
    submitLabel: isAssessment ? "평가 확인하고 비교 완료" : "후보 확인하고 다음",
  };
}

function stagePresentation(session) {
  if (session.session_kind === "prompt_ablation") {
    return ablationPresentation(session);
  }

  const isDeepReport = session.response_kind === "markdown";
  const isDeepNormalize =
    session.research_mode === "deep" &&
    session.route === "RESEARCH" &&
    session.phase !== "router" &&
    !isDeepReport;

  if (session.phase === "router") {
    return {
      step: "1단계",
      title: "방향만 정하기",
      detail: "아직 실제 조사나 결과 작성은 하지 않습니다.",
      badge: "일반 ChatGPT",
      badgeKind: "normal",
      action: "먼저 현재 라우터 지시문을 복사하세요. 그다음 ChatGPT를 열어 일반 채팅에 붙여넣고, 받은 답변 전체를 아래 칸에 넣습니다.",
      note: "이 단계에서는 심층 리서치를 켜지 않습니다. 복사와 ChatGPT 열기는 서로 다른 버튼입니다.",
      responseLabel: "ChatGPT 답변 전체 붙여넣기",
      responseHelp: "ChatGPT가 준 내용을 수정하지 말고 그대로 붙이세요.",
      responsePlaceholder: "ChatGPT 답변 전체를 여기에 붙여넣으세요.",
      submitLabel: "답변 확인하고 다음",
      copyLabel: "1. 라우터 지시문 복사",
    };
  }

  if (isDeepReport) {
    return {
      step: "2단계",
      title: "실제 조사하기",
      detail: "이번 단계에서만 ChatGPT의 심층 리서치를 사용합니다.",
      badge: "심층 리서치 켜기",
      badgeKind: "deep",
      action: "현재 조사 지시문을 복사한 뒤 ChatGPT를 열고 ‘+’ 메뉴에서 심층 리서치를 선택해 전송하세요. 조사가 끝나면 보고서 전체를 아래 칸에 붙입니다.",
      note: "JSON으로 바꾸지 말고 인용과 출처 링크가 포함된 보고서 원문을 그대로 사용합니다.",
      responseLabel: "심층 리서치 보고서 전체 붙여넣기",
      responseHelp: "완성된 보고서를 처음부터 끝까지 그대로 붙이세요.",
      responsePlaceholder: "심층 리서치가 완성한 보고서 전체를 여기에 붙여넣으세요.",
      submitLabel: "보고서 확인하고 다음",
      copyLabel: "1. 심층 조사 지시문 복사",
    };
  }

  if (isDeepNormalize) {
    return {
      step: "3단계",
      title: "결과 정리하기",
      detail: "조사 보고서를 PSOS 결과 형식으로 정리하는 마지막 단계입니다.",
      badge: "일반 ChatGPT",
      badgeKind: "normal",
      action: "현재 정리 지시문을 복사한 뒤 일반 ChatGPT에 보내세요. 이번에는 심층 리서치를 끄고 받은 JSON 전체를 아래 칸에 붙입니다.",
      note: "새 조사를 시키는 단계가 아니라 이미 완성된 보고서를 보존해 정리하는 단계입니다.",
      responseLabel: "정리된 답변 전체 붙여넣기",
      responseHelp: "ChatGPT가 반환한 JSON 전체를 그대로 붙이세요.",
      responsePlaceholder: "ChatGPT가 정리한 답변 전체를 여기에 붙여넣으세요.",
      submitLabel: "최종 결과 확인",
      copyLabel: "1. 정리 지시문 복사",
    };
  }

  const isRevision = Boolean(session.parent_run_id);
  const isResearch = session.route === "RESEARCH";
  return {
    step: session.phase === "secondary" ? "다음 단계" : (isRevision ? "수정 단계" : "2단계"),
    title: isRevision ? "피드백 반영하기" : (isResearch ? "실제 조사하기" : "실제 결과 만들기"),
    detail: isRevision
      ? "기존 결과를 기준으로 피드백을 적용한 새 전체본을 만듭니다."
      : "선택된 해결 방식으로 실제 결과를 만듭니다.",
    badge: isResearch ? "일반 ChatGPT · 웹 검색" : "일반 ChatGPT",
    badgeKind: "normal",
    action: "현재 단계의 지시문을 먼저 복사한 뒤 ChatGPT를 열어 보내고, 받은 답변 전체를 아래 칸에 붙이세요.",
    note: isResearch
      ? "필요한 웹 검색은 일반 ChatGPT에서 수행합니다. 별도로 심층 리서치를 켤 필요는 없습니다."
      : "화면에 표시된 현재 단계의 지시문인지 확인한 뒤 그대로 보내면 됩니다.",
    responseLabel: "ChatGPT 답변 전체 붙여넣기",
    responseHelp: "ChatGPT가 새로 답한 내용을 수정하지 말고 그대로 붙이세요.",
    responsePlaceholder: "ChatGPT 답변 전체를 여기에 붙여넣으세요.",
    submitLabel: session.phase === "secondary" ? "최종 결과 확인" : "답변 확인하고 계속",
    copyLabel: "1. 현재 지시문 복사",
  };
}

function applyPresentation(session) {
  const view = stagePresentation(session);
  $("#phase-step").textContent = view.step;
  $("#phase-title").textContent = view.title;
  $("#phase-detail").textContent = view.detail;
  $("#chat-mode-badge").textContent = view.badge;
  $("#chat-mode-badge").classList.toggle("deep", view.badgeKind === "deep");
  $("#action-text").textContent = view.action;
  $("#action-note").textContent = view.note;
  $("#response-label").textContent = view.responseLabel;
  $("#response-help").textContent = view.responseHelp;
  $("#response").placeholder = view.responsePlaceholder;
  submitButton.textContent = view.submitLabel;
  submitButton.dataset.label = view.submitLabel;
  copyPromptButton.textContent = view.copyLabel;
  copyPromptButton.dataset.label = view.copyLabel;
  openChatGPTButton.textContent = "2. ChatGPT 새 채팅 열기";
  openChatGPTButton.dataset.label = openChatGPTButton.textContent;
}

function showSession(session) {
  currentSession = session;
  currentRunId = session.run_id;
  localStorage.setItem("psos-current-run-id", currentRunId);
  const kindLabel = session.session_kind === "prompt_ablation" ? "구조 비교" : researchModeLabel(session.research_mode);
  $("#run-id").textContent = `${session.run_id} · ${kindLabel} · ${session.phase || session.state}`;
  $("#prompt").value = session.prompt || "";
  $("#prompt-details").open = false;
  $("#response").value = "";
  statusText.textContent = session.error || "답변을 붙여넣으면 현재 단계에 맞게 검사합니다.";
  statusText.classList.toggle("error", Boolean(session.error));

  if (session.state === "completed") {
    const isAblation = session.session_kind === "prompt_ablation";
    handoffPanel.classList.add("hidden");
    startPanel.classList.add("hidden");
    resultPanel.classList.remove("hidden");
    $("#result").textContent = session.output_markdown || session.result_markdown;
    $("#revision-research-mode").value = session.research_mode || "standard";
    $("#revision-mode").value = "preserve_route";
    updateRevisionModeHelp();
    $("#revision-box").classList.add("hidden");
    $("#revision-feedback").value = "";
    $("#revision-file").value = "";
    $("#revision-file-status").textContent = "TXT·MD 파일을 고르면 내용이 위 칸에 들어갑니다.";
    $("#result-copy-status").textContent = "";
    comparePromptButton.classList.toggle(
      "hidden",
      isAblation || session.selected_route !== "PROMPT",
    );
    backToParentButton.classList.toggle("hidden", !isAblation || !session.parent_run_id);
    showRevisionButton.classList.toggle("hidden", isAblation);
    $("#result-detail").textContent = isAblation
      ? "원본 결과를 보존한 채 네 입력 구조의 생성 결과를 비교했습니다."
      : (session.parent_run_id ? "원본을 보존한 수정 결과입니다." : "결과와 작업 기록이 저장됐습니다.");
    return;
  }

  applyPresentation(session);
  startPanel.classList.add("hidden");
  resultPanel.classList.add("hidden");
  handoffPanel.classList.remove("hidden");
}

function returnToStart({ preserveCurrentRequest = false } = {}) {
  const previousRequest = preserveCurrentRequest ? currentSession?.request || "" : "";
  const previousMode = preserveCurrentRequest ? currentSession?.research_mode || "standard" : "standard";
  currentRunId = null;
  currentSession = null;
  localStorage.removeItem("psos-current-run-id");
  $("#request").value = previousRequest;
  $("#research-mode").value = previousMode;
  updateResearchModeHelp();
  $("#revision-feedback").value = "";
  $("#revision-file").value = "";
  $("#revision-box").classList.add("hidden");
  resultPanel.classList.add("hidden");
  handoffPanel.classList.add("hidden");
  startPanel.classList.remove("hidden");
  $("#request").focus();
}

function updateResearchModeHelp() {
  const mode = $("#research-mode").value;
  $("#research-mode-help").textContent = {
    standard: "잘 모르겠으면 기본값을 사용하세요. 실제 경로는 라우터가 정하고, RESEARCH일 때만 일반 웹 검색을 사용합니다.",
    deep: "라우터 단계는 일반 ChatGPT입니다. 실제 경로가 RESEARCH일 때만 별도의 심층 조사 단계가 생깁니다.",
    none: "첨부 자료 분석, 글쓰기, 프롬프트 제작처럼 최신 외부 정보가 필요 없는 요청에 사용합니다.",
  }[mode];
}

function updateRevisionModeHelp() {
  const preserve = $("#revision-mode").value === "preserve_route";
  $("#revision-mode-help").textContent = preserve
    ? "대부분의 피드백은 이 기본값을 사용합니다. 기존 해결 방식은 유지하고 결과만 고칩니다."
    : "원래 목표를 잘못 이해했거나 결과 종류 자체를 바꿔야 할 때만 사용합니다.";
}

startButton.addEventListener("click", async () => {
  const request = $("#request").value.trim();
  if (!request) return $("#request").focus();
  setBusy(startButton, true);
  try {
    const body = await api("/api/manual/start", {
      method: "POST",
      body: JSON.stringify({
        request,
        research_mode: $("#research-mode").value,
      }),
    });
    showSession(body.session);
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(startButton, false);
  }
});

submitButton.addEventListener("click", async () => {
  const response = $("#response").value.trim();
  if (!response) return $("#response").focus();
  setBusy(submitButton, true);
  statusText.classList.remove("error");
  statusText.textContent = currentSession?.response_kind === "markdown"
    ? "보고서 내용을 검사하는 중입니다."
    : "답변 구조와 완료 조건을 검사하는 중입니다.";
  try {
    const endpoint = currentSession?.session_kind === "prompt_ablation"
      ? "/api/manual/prompt-ablation/submit"
      : "/api/manual/submit";
    const body = await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ run_id: currentRunId, response }),
    });
    showSession(body.session);
  } catch (error) {
    statusText.textContent = error.message;
    statusText.classList.add("error");
  } finally {
    setBusy(submitButton, false);
  }
});

copyPromptButton.addEventListener("click", async () => {
  const prompt = currentSession?.prompt || $("#prompt").value;
  try {
    await copyText(prompt, $("#prompt"));
    setTemporaryLabel(copyPromptButton, "복사됨 · 현재 단계 지시문");
    statusText.textContent = `${currentSession?.phase || "현재"} 단계 지시문을 복사했습니다. 이제 새 ChatGPT 채팅을 여세요.`;
    statusText.classList.remove("error");
  } catch (error) {
    $("#prompt-details").open = true;
    statusText.textContent = `${error.message} 아래 지시문을 직접 복사하세요.`;
    statusText.classList.add("error");
  }
});

openChatGPTButton.addEventListener("click", () => {
  const opened = window.open("https://chatgpt.com/", "_blank", "noopener");
  if (!opened) {
    statusText.textContent = "새 탭이 차단됐습니다. 브라우저의 팝업 허용 후 다시 누르세요.";
    statusText.classList.add("error");
  }
});

copyResultButton.addEventListener("click", async () => {
  const result = currentSession?.output_markdown || currentSession?.result_markdown || $("#result").textContent;
  try {
    await copyText(result, null);
    setTemporaryLabel(copyResultButton, "결과 복사됨");
    $("#result-copy-status").textContent = "화면에 표시된 최종 결과 전체를 복사했습니다.";
  } catch (error) {
    $("#result-copy-status").textContent = `${error.message} 결과 본문을 직접 선택해 복사하세요.`;
  }
});

comparePromptButton.addEventListener("click", async () => {
  if (!currentRunId || currentSession?.selected_route !== "PROMPT") return;
  setBusy(comparePromptButton, true);
  try {
    const body = await api("/api/manual/prompt-ablation/start", {
      method: "POST",
      body: JSON.stringify({ parent_run_id: currentRunId }),
    });
    showSession(body.session);
  } catch (error) {
    $("#result-copy-status").textContent = error.message;
  } finally {
    setBusy(comparePromptButton, false);
  }
});

backToParentButton.addEventListener("click", async () => {
  const parentRunId = currentSession?.parent_run_id;
  if (!parentRunId) return;
  setBusy(backToParentButton, true);
  try {
    const body = await api(`/api/manual/status?run_id=${encodeURIComponent(parentRunId)}`);
    showSession(body.session);
  } catch (error) {
    $("#result-copy-status").textContent = error.message;
  } finally {
    setBusy(backToParentButton, false);
  }
});

$("#abandon-run").addEventListener("click", () => {
  const leave = window.confirm("현재 작업 화면을 닫고 시작 화면으로 돌아갈까요? 기존 기록은 삭제되지 않습니다.");
  if (leave) returnToStart({ preserveCurrentRequest: true });
});

showRevisionButton.addEventListener("click", () => {
  if (currentSession?.session_kind === "prompt_ablation") return;
  $("#revision-box").classList.toggle("hidden");
  if (!$("#revision-box").classList.contains("hidden")) {
    $("#revision-feedback").focus();
  }
});

$("#research-mode").addEventListener("change", updateResearchModeHelp);
$("#revision-mode").addEventListener("change", updateRevisionModeHelp);

$("#revision-file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const status = $("#revision-file-status");
  status.textContent = `${file.name} 읽는 중…`;
  try {
    const text = await file.text();
    if (!text.trim()) throw new Error("파일이 비어 있습니다.");
    $("#revision-feedback").value = text;
    status.textContent = `${file.name} 내용을 피드백 칸에 불러왔습니다.`;
  } catch (error) {
    event.target.value = "";
    status.textContent = error.message || "파일을 읽지 못했습니다.";
  }
});

reviseButton.addEventListener("click", async () => {
  const feedback = $("#revision-feedback").value.trim();
  if (!feedback) return $("#revision-feedback").focus();
  setBusy(reviseButton, true);
  try {
    const body = await api("/api/manual/revise", {
      method: "POST",
      body: JSON.stringify({
        parent_run_id: currentRunId,
        feedback,
        revision_mode: $("#revision-mode").value,
        research_mode: $("#revision-research-mode").value,
      }),
    });
    showSession(body.session);
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(reviseButton, false);
  }
});

$("#new-run").addEventListener("click", () => {
  returnToStart();
});

async function restoreSavedSession() {
  const savedRunId = localStorage.getItem("psos-current-run-id");
  if (!savedRunId) return;
  try {
    const body = await api(`/api/manual/status?run_id=${encodeURIComponent(savedRunId)}`);
    if (body.session) showSession(body.session);
  } catch (_error) {
    localStorage.removeItem("psos-current-run-id");
  }
}

updateResearchModeHelp();
updateRevisionModeHelp();
restoreSavedSession();
