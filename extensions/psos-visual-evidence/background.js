const PSOS_BASE_URL = "http://127.0.0.1:8765";

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `PSOS 요청 실패 (${response.status})`);
  }
  return payload;
}

async function openPicker(tab) {
  if (!tab.id) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });
    const defaults = await chrome.storage.local.get({
      runId: "",
      subjectLabel: "",
      sourceKind: "unknown",
    });
    await chrome.tabs.sendMessage(tab.id, {
      type: "PSOS_VISUAL_PICKER_OPEN",
      defaults,
    });
    await chrome.action.setBadgeText({ tabId: tab.id, text: "" });
  } catch (error) {
    await chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#a2362d" });
    await chrome.action.setBadgeText({ tabId: tab.id, text: "ERR" });
    console.error("PSOS visual picker failed:", error);
  }
}

chrome.action.onClicked.addListener(openPicker);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "PSOS_IMPORT_VISUAL_EVIDENCE") return false;

  (async () => {
    const runId = String(message.runId || "").trim();
    if (!/^[A-Za-z0-9._-]+$/.test(runId)) {
      throw new Error("PSOS 실행 ID 형식이 올바르지 않습니다.");
    }
    const review = await requestJson(
      `${PSOS_BASE_URL}/api/runs/${encodeURIComponent(runId)}/evidence-review`,
    );
    const body = {
      ...message.payload,
      version: 1,
      bundle_sha256: review.bundle_sha256,
    };
    const imported = await requestJson(
      `${PSOS_BASE_URL}/api/runs/${encodeURIComponent(runId)}/visual-evidence`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    await chrome.storage.local.set({
      runId,
      subjectLabel: body.subject_label,
      sourceKind: body.source_kind,
    });
    return {
      ok: true,
      added: imported.import?.added_item_ids?.length || 0,
      subjectLabel: imported.import?.subject_label || body.subject_label,
    };
  })()
    .then(sendResponse)
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});
