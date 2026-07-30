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
    none: "웹 검색 없음",
    standard: "일반 웹 검색",
    deep: "심층 리서치",
  }[mode] || mode;
}

function configureResponseArea(session) {
  const label = $("#response-label");
  const response = $("#response");
  const responseHelp = $("#response-help");
  const callout = $("#stage-callout");

  if (session.response_kind === "markdown") {
    label.textContent = "② 심층 리서치가 완성한 보고서 전체 붙여넣기";
    responseHelp.textContent = "이번 단계에서는 JSON이 아니라 Deep research가 만든 보고서 전체를 아래 입력칸에 붙입니다.";
    response.placeholder = "Deep research가 완성한 Markdown 보고서를 처음부터 끝까지 붙여넣으세요. JSON으로 바꾸지 마세요.";
    callout.textContent = "ChatGPT에서 Deep research를 직접 켠 뒤 위 지시문을 보내세요. 이번 반환값은 JSON이 아니라 완성된 보고서입니다.";
    submitButton.textContent = "보고서 저장하고 계속";
    submitButton.dataset.label = "보고서 저장하고 계속";
    return;
  }

  label.textContent = "② ChatGPT가 반환한 JSON 붙여넣기";
  responseHelp.textContent = "위의 읽기 전용 지시문이 아니라, ChatGPT가 새로 답한 내용을 이 아래 칸에 붙여넣습니다.";
  response.placeholder = "ChatGPT의 전체 JSON 응답을 여기에 붙여넣으세요. 코드 펜스와 뒤쪽 링크 각주는 자동 정리합니다.";
  submitButton.textContent = "검증하고 계속";
  submitButton.dataset.label = "검증하고 계속";

  if (
    session.research_mode === "deep" &&
    session.route === "RESEARCH" &&
    session.phase !== "router"
  ) {
    callout.textContent = "심층 리서치 보고서는 저장됐습니다. 이번 지시문은 보고서를 PSOS execution JSON으로 정리하는 단계입니다. 일반 ChatGPT로 보내면 됩니다.";
  } else if (session.phase === "router") {
    callout.textContent = "첫 왕복입니다. 라우터 JSON이 통과하면 위 지시문과 아래 입력칸이 자동으로 다음 단계로 바뀝니다.";
  } else if (session.parent_run_id) {
    callout.textContent = "기존 결과와 수정 피드백이 지시문 안에 포함돼 있습니다. ChatGPT가 피드백을 실제로 적용한 수정 전체본을 만들면 그 JSON을 아래 ② 칸에 붙이세요.";
  } else {
    callout.textContent = "위 지시문은 이전 단계와 다른 새 작업입니다. 지시문을 ChatGPT에 보내 새 답변을 받은 뒤, 화면 아래쪽 ② 입력칸에 붙여넣으세요. 결과 수정은 이 run이 완료된 뒤 나타납니다.";
  }
}

function showSession(session) {
  currentSession = session;
  currentRunId = session.run_id;
  localStorage.setItem("psos-current-run-id", currentRunId);
  localStorage.removeItem("psos-skip-latest");
  $("#run-id").textContent = `${session.run_id} · ${researchModeLabel(session.research_mode)}`;
  $("#prompt").value = session.prompt || "";
  $("#response").value = "";
  statusText.textContent = session.error || "응답을 붙여넣으면 현재 단계에 맞게 검사합니다.";
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
    $("#revision-file-status").textContent = "TXT·MD 파일을 고르면 내용이 위 피드백 칸에 들어갑니다.";
    $("#result-detail").textContent = session.parent_run_id
      ? `원본 ${session.parent_run_id}을 보존한 revision 결과입니다.`
      : "결과와 수동 인계 기록이 run 디렉터리에 저장됐습니다.";
    return;
  }

  const isDeepReport = session.response_kind === "markdown";
  const isDeepNormalize =
    session.research_mode === "deep" &&
    session.route === "RESEARCH" &&
    session.phase !== "router" &&
    !isDeepReport;
  const labels = {
    router: ["경로 판단", "ChatGPT가 목표와 가장 작은 충분 해결 경로만 정합니다."],
    primary: ["실제 결과 생성", "선택된 경로의 결과를 JSON으로 돌려받습니다."],
    secondary: ["보조 경로 실행", "주 경로 결과를 이어받아 최종 결과를 완성합니다."],
  };
  let titleDetail = labels[session.phase] || ["ChatGPT에 전달", "아래 지시문을 전달하세요."];
  if (isDeepReport) {
    titleDetail = ["심층 리서치 실행", "Deep research로 조사한 완성 보고서를 그대로 돌려받습니다."];
  } else if (isDeepNormalize) {
    titleDetail = ["보고서 정규화", "저장된 심층 리서치 보고서를 PSOS JSON으로 변환합니다."];
  } else if (session.parent_run_id && session.phase !== "router") {
    titleDetail = ["결과 직접 수정", "직전 결과에 피드백을 적용한 수정 전체본을 만듭니다."];
  }
  $("#phase-title").textContent = titleDetail[0];
  $("#phase-detail").textContent = titleDetail[1];
  configureResponseArea(session);
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
  $("#revision-feedback").value = "";
  $("#revision-file").value = "";
  $("#revision-box").classList.add("hidden");
  resultPanel.classList.add("hidden");
  handoffPanel.classList.add("hidden");
  startPanel.classList.remove("hidden");
  $("#request").focus();
}

function updateRevisionModeHelp() {
  const preserve = $("#revision-mode").value === "preserve_route";
  $("#revision-mode-help").textContent = preserve
    ? "문장 교체·규칙 추가·항목 삭제처럼 기존 산출물을 개선하는 피드백은 이 기본값을 사용합니다. 라우터를 다시 거치지 않습니다."
    : "원래 목표를 잘못 이해했거나 산출물 종류 자체를 바꿔야 할 때만 사용합니다. 라우터부터 다시 실행합니다.";
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
    ? "보고서를 저장하고 정규화 지시문을 만드는 중입니다."
    : "JSON 구조와 PSOS 완료 조건을 검사하는 중입니다.";
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

$("#copy-prompt").addEventListener("click", async () => {
  await navigator.clipboard.writeText($("#prompt").value);
  const button = $("#copy-prompt");
  const original = button.textContent;
  button.textContent = "복사됨";
  setTimeout(() => { button.textContent = original; }, 1000);
});

$("#open-chatgpt").addEventListener("click", () => {
  window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
});

$("#abandon-run").addEventListener("click", () => {
  const leave = window.confirm("현재 작업 화면을 닫고 새 요청으로 돌아갈까요? 기존 run 기록은 삭제되지 않습니다.");
  if (leave) returnToStart({ preserveCurrentRequest: true });
});

$("#show-revision").addEventListener("click", () => {
  $("#revision-box").classList.toggle("hidden");
  if (!$("#revision-box").classList.contains("hidden")) {
    $("#revision-feedback").focus();
  }
});

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
    // The start panel remains usable when no previous session can be restored.
  }
}

updateRevisionModeHelp();
restoreLastSession();
