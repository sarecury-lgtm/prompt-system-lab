const $ = (selector) => document.querySelector(selector);

const startPanel = $("#start-panel");
const handoffPanel = $("#handoff-panel");
const resultPanel = $("#result-panel");
const startButton = $("#start");
const submitButton = $("#submit");
const reviseButton = $("#revise");
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

function researchModeLabel(mode) {
  return {
    none: "검색 없음",
    standard: "일반 조사",
    deep: "심층 조사",
  }[mode] || mode;
}

function stagePresentation(session) {
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
      action: "버튼을 누르면 지시문이 복사되고 ChatGPT가 열립니다. 일반 채팅에 그대로 보내고, 받은 답변 전체를 아래 칸에 붙이세요.",
      note: "이 단계에서는 심층 리서치를 켜지 않습니다.",
      responseLabel: "ChatGPT 답변 전체 붙여넣기",
      responseHelp: "ChatGPT가 준 내용을 수정하지 말고 그대로 붙이세요.",
      responsePlaceholder: "ChatGPT 답변 전체를 여기에 붙여넣으세요.",
      submitLabel: "답변 확인하고 다음",
    };
  }

  if (isDeepReport) {
    return {
      step: "2단계",
      title: "실제 조사하기",
      detail: "이번 단계에서만 ChatGPT의 심층 리서치를 사용합니다.",
      badge: "심층 리서치 켜기",
      badgeKind: "deep",
      action: "버튼을 누른 뒤 열린 ChatGPT에서 ‘+’ 메뉴의 심층 리서치를 선택해 전송하세요. 조사가 끝나면 완성된 보고서 전체를 아래 칸에 붙이세요.",
      note: "JSON으로 바꾸지 말고 보고서 원문을 처음부터 끝까지 붙입니다.",
      responseLabel: "심층 리서치 보고서 전체 붙여넣기",
      responseHelp: "인용과 출처 링크가 포함된 완성 보고서를 그대로 붙이세요.",
      responsePlaceholder: "심층 리서치가 완성한 보고서 전체를 여기에 붙여넣으세요.",
      submitLabel: "보고서 확인하고 다음",
    };
  }

  if (isDeepNormalize) {
    return {
      step: "3단계",
      title: "결과 정리하기",
      detail: "조사 보고서를 PSOS 결과 형식으로 정리하는 마지막 단계입니다.",
      badge: "일반 ChatGPT",
      badgeKind: "normal",
      action: "버튼을 눌러 이번 지시문을 일반 ChatGPT에 보내세요. 받은 답변 전체를 아래 칸에 붙이면 완료됩니다.",
      note: "이번에는 심층 리서치를 끄고 일반 채팅으로 보냅니다.",
      responseLabel: "정리된 답변 전체 붙여넣기",
      responseHelp: "ChatGPT가 반환한 JSON 전체를 그대로 붙이세요.",
      responsePlaceholder: "ChatGPT가 정리한 답변 전체를 여기에 붙여넣으세요.",
      submitLabel: "최종 결과 확인",
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
    action: "버튼을 눌러 지시문을 일반 ChatGPT에 보내고, 받은 답변 전체를 아래 칸에 붙이세요.",
    note: isResearch
      ? "ChatGPT가 필요한 웹 검색을 수행합니다. 별도로 심층 리서치를 켤 필요는 없습니다."
      : "화면에 나온 지시문을 수정하지 않고 그대로 보내면 됩니다.",
    responseLabel: "ChatGPT 답변 전체 붙여넣기",
    responseHelp: "ChatGPT가 새로 답한 내용을 수정하지 말고 그대로 붙이세요.",
    responsePlaceholder: "ChatGPT 답변 전체를 여기에 붙여넣으세요.",
    submitLabel: session.phase === "secondary" ? "최종 결과 확인" : "답변 확인하고 계속",
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
  $("#send-to-chatgpt").textContent = view.badgeKind === "deep"
    ? "복사하고 ChatGPT 열기 · 심층 리서치 사용"
    : "지시문 복사하고 ChatGPT 열기";
  $("#send-to-chatgpt").dataset.label = $("#send-to-chatgpt").textContent;
}

function showSession(session) {
  currentSession = session;
  currentRunId = session.run_id;
  localStorage.setItem("psos-current-run-id", currentRunId);
  localStorage.removeItem("psos-skip-latest");
  $("#run-id").textContent = `${session.run_id} · ${researchModeLabel(session.research_mode)}`;
  $("#prompt").value = session.prompt || "";
  $("#prompt-details").open = false;
  $("#response").value = "";
  statusText.textContent = session.error || "답변을 붙여넣으면 현재 단계에 맞게 검사합니다.";
  statusText.classList.toggle("error", Boolean(session.error));

  if (session.state === "completed") {
    handoffPanel.classList.add("hidden");
    startPanel.classList.add("hidden");
    resultPanel.classList.remove("hidden");
    $("#result").textContent = session.result_markdown;
    $("#revision-research-mode").value = session.research_mode || "standard";
    $("#revision-mode").value = "preserve_route";
    updateRevisionModeHelp();
    $("#revision-box").classList.add("hidden");
    $("#revision-feedback").value = "";
    $("#revision-file").value = "";
    $("#revision-file-status").textContent = "TXT·MD 파일을 고르면 내용이 위 칸에 들어갑니다.";
    $("#result-detail").textContent = session.parent_run_id
      ? "원본을 보존한 수정 결과입니다."
      : "결과와 작업 기록이 저장됐습니다.";
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
  localStorage.setItem("psos-skip-latest", "1");
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
    standard: "잘 모르겠으면 이 기본값을 사용하세요. 필요한 웹 검색은 실제 결과 단계에서 ChatGPT가 수행합니다.",
    deep: "첫 단계는 여전히 일반 ChatGPT입니다. 실제 조사 단계가 되면 화면에 ‘심층 리서치 켜기’라고 크게 표시됩니다.",
    none: "최신 정보나 외부 출처가 필요 없는 작성·분석 요청에 사용합니다.",
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
    const body = await api("/api/manual/submit", {
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

$("#send-to-chatgpt").addEventListener("click", async () => {
  const button = $("#send-to-chatgpt");
  const original = button.dataset.label || button.textContent;
  const opened = window.open("https://chatgpt.com/", "_blank");
  if (opened) opened.opener = null;

  let copied = false;
  try {
    await navigator.clipboard.writeText($("#prompt").value);
    copied = true;
  } catch (_error) {
    $("#prompt-details").open = true;
    $("#prompt").focus();
    $("#prompt").select();
    copied = document.execCommand("copy");
  }

  button.textContent = copied
    ? "복사됨 · ChatGPT에 붙여넣으세요"
    : "복사 실패 · 아래 지시문을 직접 복사하세요";
  if (!copied) $("#prompt-details").open = true;
  setTimeout(() => { button.textContent = original; }, 1800);
});

$("#abandon-run").addEventListener("click", () => {
  const leave = window.confirm("현재 작업 화면을 닫고 시작 화면으로 돌아갈까요? 기존 기록은 삭제되지 않습니다.");
  if (leave) returnToStart({ preserveCurrentRequest: true });
});

$("#show-revision").addEventListener("click", () => {
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

async function restoreLastSession() {
  const savedRunId = localStorage.getItem("psos-current-run-id");
  if (savedRunId) {
    try {
      const body = await api(`/api/manual/status?run_id=${encodeURIComponent(savedRunId)}`);
      if (body.session) {
        showSession(body.session);
        return;
      }
    } catch (_error) {
      localStorage.removeItem("psos-current-run-id");
    }
  }
  if (localStorage.getItem("psos-skip-latest") === "1") return;
  try {
    const active = await api("/api/manual/active");
    if (active.session) {
      showSession(active.session);
      return;
    }
    const latest = await api("/api/manual/latest");
    if (latest.session) showSession(latest.session);
  } catch (_error) {
    // No saved session: keep the start panel visible.
  }
}

updateResearchModeHelp();
updateRevisionModeHelp();
restoreLastSession();
