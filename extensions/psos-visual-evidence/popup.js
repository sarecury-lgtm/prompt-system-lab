const PSOS_BASE_URL = "http://127.0.0.1:8765";
const runIdInput = document.querySelector("#run-id");
const startButton = document.querySelector("#start");
const resumeButton = document.querySelector("#resume");
const visualButton = document.querySelector("#visual");
const progress = document.querySelector("#progress");
const stateNode = document.querySelector("#state");
const countNode = document.querySelector("#count");
const bar = document.querySelector("#bar");
const messageNode = document.querySelector("#message");

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `PSOS 요청 실패 (${response.status})`);
  return payload;
}

function runId() {
  const value = runIdInput.value.trim();
  if (!/^[A-Za-z0-9._-]+$/.test(value)) throw new Error("PSOS 실행 ID를 확인해 주세요.");
  return value;
}

function renderQueue(queue) {
  if (!queue) return;
  progress.hidden = false;
  const counts = queue.counts || {};
  stateNode.textContent = {
    pending: "검증 대기",
    needs_user: "사용자 확인 필요",
    completed: "검증 완료",
  }[queue.state] || queue.state;
  countNode.textContent = `${counts.completed || 0} / ${counts.total || 0}`;
  bar.max = Math.max(1, counts.total || 1);
  bar.value = counts.completed || 0;
}

function setBusy(busy) {
  startButton.disabled = busy;
  resumeButton.disabled = busy;
  visualButton.disabled = busy;
}

function showMessage(text, error = false) {
  messageNode.textContent = text;
  messageNode.classList.toggle("error", error);
}

async function requestPageAccess() {
  const allowed = await chrome.permissions.request({ origins: ["http://*/*", "https://*/*"] });
  if (!allowed) throw new Error("상품 페이지를 확인하려면 웹사이트 접근 권한이 필요합니다.");
}

async function runVerification(create) {
  setBusy(true);
  showMessage("Chrome 연결을 준비하고 있습니다.");
  try {
    await requestPageAccess();
    const id = runId();
    await chrome.storage.local.set({ runId: id });
    const queue = create
      ? await requestJson(`${PSOS_BASE_URL}/api/runs/${encodeURIComponent(id)}/browser-verification`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reset: false }),
        })
      : await requestJson(`${PSOS_BASE_URL}/api/runs/${encodeURIComponent(id)}/browser-verification`);
    renderQueue(queue);
    showMessage("상품 페이지를 순서대로 확인하고 있습니다. 완료될 때까지 이 창을 열어 두세요.");
    const response = await chrome.runtime.sendMessage({
      type: "PSOS_START_PRODUCT_VERIFICATION",
      runId: id,
      targets: queue.targets,
    });
    if (!response?.ok) throw new Error(response?.error || "Chrome 검증을 시작하지 못했습니다.");
    renderQueue(response.queue);
    showMessage(response.message || "검증을 마쳤습니다.");
  } catch (error) {
    showMessage(error?.message || String(error), true);
  } finally {
    setBusy(false);
  }
}

startButton.addEventListener("click", () => runVerification(true));
resumeButton.addEventListener("click", () => runVerification(false));
visualButton.addEventListener("click", async () => {
  setBusy(true);
  try {
    const response = await chrome.runtime.sendMessage({ type: "PSOS_OPEN_VISUAL_PICKER" });
    if (!response?.ok) throw new Error(response?.error || "사진 근거 도구를 열지 못했습니다.");
    window.close();
  } catch (error) {
    showMessage(error?.message || String(error), true);
    setBusy(false);
  }
});

(async () => {
  const saved = await chrome.storage.local.get({ runId: "" });
  runIdInput.value = saved.runId || "";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^http:\/\/(?:127\.0\.0\.1|localhost):8765\//.test(tab.url || "")) return;
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.querySelector("#run-id")?.textContent?.trim() || "",
    });
    if (/^[A-Za-z0-9._-]+$/.test(result || "")) runIdInput.value = result;
  } catch (_error) {
    // Saved run ID remains the fallback when the PSOS tab is not active.
  }
})();
