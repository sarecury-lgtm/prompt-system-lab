const serverInput = document.querySelector("#server");
const status = document.querySelector("#status");

function setStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle("error", error);
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.startsWith("https://chatgpt.com/")) {
    throw new Error("현재 탭이 chatgpt.com이 아닙니다.");
  }
  return tab;
}

async function sendToTab(message) {
  const tab = await activeTab();
  const result = await chrome.tabs.sendMessage(tab.id, message);
  if (!result?.ok) throw new Error(result?.error || "ChatGPT 탭과 통신하지 못했습니다.");
  return result;
}

async function bridge(path, options = {}) {
  const base = serverInput.value.trim().replace(/\/$/, "");
  const response = await fetch(base + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `브리지 HTTP ${response.status}`);
  return body;
}

async function saveServer() {
  await chrome.storage.local.set({ psosServer: serverInput.value.trim() });
}

chrome.storage.local.get("psosServer").then(({ psosServer }) => {
  if (psosServer) serverInput.value = psosServer;
});
serverInput.addEventListener("change", saveServer);

async function insertSession(session) {
  if (!session) throw new Error("대기 중인 PSOS 수동 작업이 없습니다.");
  await sendToTab({ type: "PSOS_INSERT_PROMPT", prompt: session.prompt });
  await chrome.storage.local.set({ psosRunId: session.run_id });
  setStatus(`${session.phase || "다음"} 지시문을 입력했습니다.\nChatGPT에서 전송 버튼을 누르세요.`);
}

document.querySelector("#insert").addEventListener("click", async () => {
  try {
    setStatus("대기 중 작업을 확인하는 중…");
    await saveServer();
    const body = await bridge("/api/manual/active");
    await insertSession(body.session);
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.querySelector("#return").addEventListener("click", async () => {
  try {
    setStatus("마지막 답변을 읽는 중…");
    await saveServer();
    const extracted = await sendToTab({ type: "PSOS_EXTRACT_LAST_RESPONSE" });
    const { psosRunId } = await chrome.storage.local.get("psosRunId");
    if (!psosRunId) throw new Error("연결된 PSOS run-id가 없습니다. 먼저 작업을 가져오세요.");
    const body = await bridge("/api/manual/submit", {
      method: "POST",
      body: JSON.stringify({ run_id: psosRunId, response: extracted.response }),
    });
    if (body.session.state === "completed") {
      setStatus("PSOS 검증과 저장이 완료됐습니다.");
      return;
    }
    await insertSession(body.session);
  } catch (error) {
    setStatus(error.message, true);
  }
});
