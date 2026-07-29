const $ = (selector) => document.querySelector(selector);

const startPanel = $("#start-panel");
const handoffPanel = $("#handoff-panel");
const resultPanel = $("#result-panel");
const startButton = $("#start");
const submitButton = $("#submit");
const statusText = $("#status");
let currentRunId = null;

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

function showSession(session) {
  currentRunId = session.run_id;
  $("#run-id").textContent = session.run_id;
  $("#prompt").value = session.prompt || "";
  $("#response").value = "";
  statusText.textContent = session.error || "응답을 붙여넣으면 기존 PSOS validator로 검사합니다.";
  statusText.classList.toggle("error", Boolean(session.error));

  if (session.state === "completed") {
    handoffPanel.classList.add("hidden");
    resultPanel.classList.remove("hidden");
    $("#result").textContent = session.result_markdown;
    return;
  }

  const labels = {
    router: ["경로 판단", "ChatGPT가 목표와 가장 작은 충분 해결 경로만 정합니다."],
    primary: ["실제 결과 생성", "선택된 경로의 결과를 JSON으로 돌려받습니다."],
    secondary: ["보조 경로 실행", "주 경로 결과를 이어받아 최종 결과를 완성합니다."],
  };
  const [title, detail] = labels[session.phase] || ["ChatGPT에 전달", "아래 지시문을 전달하세요."];
  $("#phase-title").textContent = title;
  $("#phase-detail").textContent = detail;
  startPanel.classList.add("hidden");
  resultPanel.classList.add("hidden");
  handoffPanel.classList.remove("hidden");
}

startButton.addEventListener("click", async () => {
  const request = $("#request").value.trim();
  if (!request) return $("#request").focus();
  setBusy(startButton, true);
  try {
    const body = await api("/api/manual/start", {
      method: "POST",
      body: JSON.stringify({ request, search_enabled: $("#search-enabled").checked }),
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
  statusText.textContent = "JSON 구조와 PSOS 완료 조건을 검사하는 중입니다.";
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

$("#new-run").addEventListener("click", () => {
  currentRunId = null;
  $("#request").value = "";
  resultPanel.classList.add("hidden");
  handoffPanel.classList.add("hidden");
  startPanel.classList.remove("hidden");
  $("#request").focus();
});
