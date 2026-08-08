(() => {
  if (typeof elements === "undefined") return;

  const guide = document.querySelector("#workflow-guide");
  if (!guide || document.querySelector("#psos-blind-handoff")) return;

  const card = document.createElement("section");
  card.id = "psos-blind-handoff";
  card.className = "psos-blind-handoff";
  card.innerHTML = `
    <div class="psos-blind-handoff-copy">
      <span class="workflow-kicker">Codex가 막혔을 때</span>
      <strong>PSOS Blind로 한 번 넘기기</strong>
      <p>현재 요청·결과·첨부를 ZIP 하나로 묶습니다. PSOS Blind 채팅에 한 번 올린 뒤 그 채팅에서 계속 대화하세요.</p>
      <span id="psos-blind-handoff-status" role="status" aria-live="polite"></span>
    </div>
    <div class="psos-blind-handoff-actions">
      <button id="psos-blind-handoff-export" type="button">handoff ZIP 만들기</button>
      <button id="psos-blind-handoff-open" type="button" class="secondary-button">ChatGPT 열기</button>
    </div>
  `;
  guide.insertAdjacentElement("afterend", card);

  const exportButton = card.querySelector("#psos-blind-handoff-export");
  const openButton = card.querySelector("#psos-blind-handoff-open");
  const status = card.querySelector("#psos-blind-handoff-status");

  function currentResult() {
    if (!elements.completed || elements.completed.hidden) return "";
    return String(elements.resultContent?.innerText || "").trim().slice(0, 20000);
  }

  function attachmentPaths(request) {
    const text = String(request || "");
    const marker = text.indexOf("[첨부 시각 자료]");
    if (marker < 0) return [];
    const block = text.slice(marker);
    const result = [];
    for (const match of block.matchAll(/^-\s+[^:\n]+:\s+(.+)$/gm)) {
      const value = String(match[1] || "").trim();
      if (value && !result.includes(value)) result.push(value);
    }
    return result.slice(0, 4);
  }

  function manualState({ hasCurrentResult = false } = {}) {
    try {
      const saved = JSON.parse(window.localStorage.getItem("psos-manual-job-workflow-v1") || "null");
      if (!saved || typeof saved !== "object") return {};
      const envelope =
        saved.imported?.envelope && typeof saved.imported.envelope === "object"
          ? {
              status: saved.imported.envelope.status || null,
              route: saved.imported.envelope.route || null,
              completion: saved.imported.envelope.completion || null,
              continuation: saved.imported.envelope.continuation || null,
            }
          : null;
      return {
        latest_answer:
          !hasCurrentResult && typeof saved.answer === "string"
            ? saved.answer.slice(0, 12000)
            : "",
        latest_correction:
          typeof saved.correction === "string" ? saved.correction.slice(0, 8000) : "",
        imported: envelope ? { envelope, warnings: [] } : null,
      };
    } catch (_error) {
      return {};
    }
  }

  function filenameFromDisposition(value) {
    const match = String(value || "").match(/filename="?([^";]+)"?/i);
    return match ? match[1] : "psos-blind-handoff.zip";
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportHandoff() {
    const request = String(elements.request?.value || "").trim();
    if (!request) {
      status.textContent = "먼저 작업실에 요청을 입력해 주세요.";
      elements.request?.focus();
      return;
    }

    const result = currentResult();
    exportButton.disabled = true;
    status.textContent = "현재 작업 상태를 ZIP으로 묶고 있습니다.";
    try {
      const response = await fetch("/api/blind-handoff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          current_result: result,
          route: String(elements.route?.textContent || "").trim(),
          run_id: String(elements.runId?.textContent || "").trim(),
          manual_state: manualState({ hasCurrentResult: Boolean(result) }),
          attachment_paths: attachmentPaths(request),
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `handoff 실패 (${response.status})`);
      }
      const blob = await response.blob();
      const filename = filenameFromDisposition(response.headers.get("Content-Disposition"));
      downloadBlob(blob, filename);
      status.textContent = "ZIP을 만들었습니다. PSOS Blind 채팅에 이 파일을 한 번 올린 뒤 그 채팅에서 계속 대화하면 됩니다.";
    } catch (error) {
      status.textContent = error.message || "handoff ZIP을 만들지 못했습니다.";
    } finally {
      exportButton.disabled = false;
    }
  }

  function openChatGPT() {
    const opened = window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
    status.textContent = opened
      ? "ChatGPT를 열었습니다. PSOS Blind를 선택하고 방금 만든 ZIP을 한 번 올리세요."
      : "팝업이 차단됐습니다. ChatGPT를 직접 열어 주세요.";
  }

  exportButton.addEventListener("click", exportHandoff);
  openButton.addEventListener("click", openChatGPT);

  window.PSOSBlindHandoff = Object.freeze({
    version: 1,
    exportCurrent: exportHandoff,
  });
})();
