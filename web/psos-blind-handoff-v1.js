(() => {
  if (typeof elements === "undefined") return;

  const guide = document.querySelector("#workflow-guide");
  if (!guide || document.querySelector("#psos-blind-handoff")) return;

  const REPOSITORY = "sarecury-lgtm/prompt-system-lab";
  const BRANCH = "codex/problem-solving-os-next-loop";

  const card = document.createElement("section");
  card.id = "psos-blind-handoff";
  card.className = "psos-blind-handoff";
  card.innerHTML = `
    <div class="psos-blind-handoff-copy">
      <span class="workflow-kicker">Codex가 막혔을 때 기본 fallback</span>
      <strong>PSOS Blind + GitHub로 이어서 작업</strong>
      <p>Git에 있는 코드·문서·작업 상태는 다시 묶지 않습니다. PSOS Blind가 GitHub Action으로 현재 브랜치와 ACTIVE_GOAL.json을 읽고 같은 작업을 계속합니다.</p>
      <span id="psos-blind-handoff-status" role="status" aria-live="polite"></span>
    </div>
    <div class="psos-blind-handoff-actions">
      <button id="psos-blind-handoff-copy" type="button">Blind handoff 지시문 복사</button>
      <button id="psos-blind-handoff-open" type="button" class="secondary-button">ChatGPT 열기</button>
      <button id="psos-blind-handoff-export" type="button" class="secondary-button" hidden>보조 ZIP 만들기</button>
    </div>
  `;
  guide.insertAdjacentElement("afterend", card);

  const copyButton = card.querySelector("#psos-blind-handoff-copy");
  const openButton = card.querySelector("#psos-blind-handoff-open");
  const exportButton = card.querySelector("#psos-blind-handoff-export");
  const status = card.querySelector("#psos-blind-handoff-status");

  function currentRequest() {
    return String(elements.request?.value || "").trim();
  }

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
    for (const match of block.matchAll(/^\-\s+[^:\n]+:\s+(.+)$/gm)) {
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

  function supplementalContext() {
    const request = currentRequest();
    const result = currentResult();
    const manual = manualState({ hasCurrentResult: Boolean(result) });
    const attachments = attachmentPaths(request);
    return {
      result,
      manual,
      attachments,
      useful:
        Boolean(result) ||
        attachments.length > 0 ||
        Boolean(manual.latest_answer) ||
        Boolean(manual.latest_correction) ||
        Boolean(manual.imported),
    };
  }

  function syncSupplementalZip() {
    const supplemental = supplementalContext();
    exportButton.hidden = !supplemental.useful;
    exportButton.title = supplemental.useful
      ? "Git에 없는 현재 대화 결과·교정·첨부를 보조 ZIP으로 넘깁니다."
      : "Git에 없는 추가 대화 상태나 첨부가 생기면 사용할 수 있습니다.";
  }

  function buildHandoffPrompt() {
    const request = currentRequest();
    const supplemental = supplementalContext();
    const lines = [
      "PSOS Blind로 이 작업을 이어서 처리해줘.",
      `GitHub Action으로 ${REPOSITORY} 저장소의 ${BRANCH} 브랜치를 읽고, 먼저 ACTIVE_GOAL.json과 현재 작업 관련 파일을 확인해.`,
      "Git에 있는 코드·문서·상태는 이 메시지나 ZIP을 기준으로 추측하지 말고 GitHub의 현재 브랜치를 source of truth로 사용해.",
      "현재 브라우저 요청:",
      request || "(브라우저 요청 없음)",
    ];
    if (supplemental.useful) {
      lines.push(
        "",
        "현재 결과·교정·첨부처럼 Git에 없는 추가 상태가 필요하면 함께 제공하는 보조 ZIP만 그 부분의 근거로 사용해.",
      );
    }
    return lines.join("\n");
  }

  async function copyReliable(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_error) {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand("copy");
      textarea.remove();
      return copied;
    }
  }

  async function copyHandoff() {
    if (!currentRequest()) {
      status.textContent = "먼저 작업실에 요청을 입력해 주세요.";
      elements.request?.focus();
      return;
    }
    const copied = await copyReliable(buildHandoffPrompt());
    status.textContent = copied
      ? "Blind handoff 지시문을 복사했습니다. PSOS Blind 채팅에 붙여 넣으세요."
      : "복사에 실패했습니다. 브라우저의 클립보드 권한을 확인해 주세요.";
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
    const request = currentRequest();
    if (!request) {
      status.textContent = "먼저 작업실에 요청을 입력해 주세요.";
      elements.request?.focus();
      return;
    }
    const supplemental = supplementalContext();
    if (!supplemental.useful) {
      syncSupplementalZip();
      status.textContent = "추가 ZIP은 필요하지 않습니다. Git 상태는 PSOS Blind가 GitHub에서 직접 읽습니다.";
      return;
    }

    exportButton.disabled = true;
    status.textContent = "Git에 없는 대화 상태와 첨부만 보조 ZIP으로 묶고 있습니다.";
    try {
      const response = await fetch("/api/blind-handoff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          current_result: supplemental.result,
          route: String(elements.route?.textContent || "").trim(),
          run_id: String(elements.runId?.textContent || "").trim(),
          manual_state: supplemental.manual,
          attachment_paths: supplemental.attachments,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `handoff 실패 (${response.status})`);
      }
      const blob = await response.blob();
      const filename = filenameFromDisposition(response.headers.get("Content-Disposition"));
      downloadBlob(blob, filename);
      status.textContent = "보조 ZIP을 만들었습니다. PSOS Blind에는 Git에 없는 대화 상태나 첨부를 보충할 때만 사용하세요.";
    } catch (error) {
      status.textContent = error.message || "보조 ZIP을 만들지 못했습니다.";
    } finally {
      exportButton.disabled = false;
    }
  }

  function openChatGPT() {
    const opened = window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
    status.textContent = opened
      ? "ChatGPT를 열었습니다. PSOS Blind를 선택하고 복사한 handoff 지시문을 붙여 넣으세요."
      : "팝업이 차단됐습니다. ChatGPT를 직접 열어 주세요.";
  }

  copyButton.addEventListener("click", copyHandoff);
  openButton.addEventListener("click", openChatGPT);
  exportButton.addEventListener("click", exportHandoff);

  elements.request?.addEventListener("input", syncSupplementalZip);
  if (elements.completed) {
    new MutationObserver(syncSupplementalZip).observe(elements.completed, {
      attributes: true,
      attributeFilter: ["hidden"],
    });
  }
  if (elements.resultContent) {
    new MutationObserver(syncSupplementalZip).observe(elements.resultContent, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }
  syncSupplementalZip();

  window.PSOSBlindHandoff = Object.freeze({
    version: 2,
    copyCurrent: copyHandoff,
    exportCurrent: exportHandoff,
    buildPrompt: buildHandoffPrompt,
  });
})();
