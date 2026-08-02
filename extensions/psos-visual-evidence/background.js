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
  if (!tab?.id) throw new Error("사진을 고를 Chrome 탭이 없습니다.");
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
}

function waitForTab(tabId, timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error("상품 페이지가 45초 안에 열리지 않았습니다."));
    }, timeoutMs);
    const listener = (updatedId, changeInfo, tab) => {
      if (updatedId !== tabId || changeInfo.status !== "complete") return;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(tab);
    };
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((tab) => {
      if (tab.status === "complete") {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(tab);
      }
    }).catch(() => {});
  });
}

async function findExistingTab(url) {
  const tabs = await chrome.tabs.query({});
  return tabs.find((tab) => tab.url === url) || null;
}

async function inspectTarget(target) {
  let tab = await findExistingTab(target.url);
  let created = false;
  if (!tab?.id) {
    tab = await chrome.tabs.create({ url: target.url, active: false });
    created = true;
  }
  try {
    await waitForTab(tab.id);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["product-verifier.js"],
    });
    const receipt = await chrome.tabs.sendMessage(tab.id, {
      type: "PSOS_VERIFY_PRODUCT_PAGE",
      expectedUrl: target.url,
    });
    if (!receipt) throw new Error("상품 페이지 검증 결과가 비어 있습니다.");
    if (receipt.status === "needs_user") {
      await chrome.tabs.update(tab.id, { active: true });
      return { receipt, paused: true, tabId: tab.id };
    }
    if (created) await chrome.tabs.remove(tab.id).catch(() => {});
    return { receipt, paused: false, tabId: tab.id };
  } catch (error) {
    if (created) await chrome.tabs.remove(tab.id).catch(() => {});
    return {
      paused: false,
      tabId: tab.id,
      receipt: {
        url: target.url,
        final_url: tab.url || target.url,
        status: "error",
        checked_at: new Date().toISOString(),
        signal: "extension_error",
        excerpt: String(error?.message || error),
        fields: {},
      },
    };
  }
}

async function postReceipt(runId, target, receipt) {
  return requestJson(
    `${PSOS_BASE_URL}/api/runs/${encodeURIComponent(runId)}/browser-verification/${encodeURIComponent(target.id)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(receipt),
    },
  );
}

async function processVerification(runId, suppliedTargets) {
  const current = await requestJson(
    `${PSOS_BASE_URL}/api/runs/${encodeURIComponent(runId)}/browser-verification`,
  );
  const allowedIds = new Set((suppliedTargets || []).map((item) => item.id));
  const targets = current.targets.filter(
    (item) =>
      (!allowedIds.size || allowedIds.has(item.id)) &&
      ["pending", "needs_user"].includes(item.status),
  );
  if (!targets.length) return { ok: true, queue: current, message: "검증할 항목이 없습니다." };

  let latest = { queue: current, revision: null };
  for (const target of targets) {
    const inspected = await inspectTarget(target);
    latest = await postReceipt(runId, target, inspected.receipt);
    if (inspected.paused) {
      return {
        ok: true,
        paused: true,
        queue: latest.queue,
        message: "로그인 또는 사람 확인이 필요합니다. 열린 탭에서 마친 뒤 ‘이어서 검증’을 누르세요.",
      };
    }
  }
  return {
    ok: true,
    paused: false,
    queue: latest.queue,
    revision: latest.revision,
    message: latest.revision
      ? `검증을 마쳤고 수정 실행 ${latest.revision.run_id}을 시작했습니다.`
      : "현재 대기열 검증을 마쳤습니다.",
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PSOS_OPEN_VISUAL_PICKER") {
    (async () => {
      const tab = sender.tab || (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
      await openPicker(tab);
      return { ok: true };
    })().then(sendResponse).catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "PSOS_START_PRODUCT_VERIFICATION") {
    processVerification(String(message.runId || "").trim(), message.targets || [])
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

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
