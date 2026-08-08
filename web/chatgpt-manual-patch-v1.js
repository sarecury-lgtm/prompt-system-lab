(() => {
  if (typeof showCompleted !== "function") return;
  const importedSection = document.querySelector("#manual-v5-imported");
  const envelopeNode = document.querySelector("#manual-v5-envelope");
  const importButton = document.querySelector("#manual-v5-import");
  const requestField = document.querySelector("#manual-v5-request");
  if (!importedSection || !envelopeNode || !importButton || !requestField) return;

  const state = {
    envelope: null,
    operations: [],
    preview: null,
  };

  const panel = document.createElement("section");
  panel.id = "manual-patch-panel";
  panel.className = "manual-v5-step manual-patch-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="manual-v5-step-head">
      <div>
        <strong>파일 변경안</strong>
        <p id="manual-patch-summary">ChatGPT가 반환한 전체 파일 변경안을 로컬에서 검증합니다.</p>
      </div>
      <span id="manual-patch-badge" class="workflow-badge">검토 전</span>
    </div>

    <div class="manual-patch-grid">
      <label class="field-label" for="manual-patch-scopes">
        <span>변경을 허용할 파일 또는 폴더</span>
        <textarea id="manual-patch-scopes" rows="5" placeholder="한 줄에 하나"></textarea>
      </label>
      <label class="field-label" for="manual-patch-tests">
        <span>적용 후 검사 명령</span>
        <textarea id="manual-patch-tests" rows="5" placeholder="비워 두면 변경한 Python·JavaScript 파일의 문법을 자동 검사합니다."></textarea>
      </label>
    </div>

    <details class="manual-v5-details" open>
      <summary>변경 파일 보기</summary>
      <ul id="manual-patch-files"></ul>
    </details>

    <div class="manual-v5-step-head manual-patch-actions-row">
      <span id="manual-patch-status" role="status" aria-live="polite"></span>
      <div class="manual-v5-actions">
        <button id="manual-patch-preview" type="button">변경 검토</button>
        <button id="manual-patch-cancel" type="button" class="secondary-button" hidden>취소</button>
        <button id="manual-patch-execute" type="button" class="danger-button" hidden>검토한 변경 적용</button>
      </div>
    </div>
  `;
  importedSection.insertAdjacentElement("afterend", panel);

  const summary = panel.querySelector("#manual-patch-summary");
  const badge = panel.querySelector("#manual-patch-badge");
  const scopes = panel.querySelector("#manual-patch-scopes");
  const tests = panel.querySelector("#manual-patch-tests");
  const files = panel.querySelector("#manual-patch-files");
  const status = panel.querySelector("#manual-patch-status");
  const previewButton = panel.querySelector("#manual-patch-preview");
  const cancelButton = panel.querySelector("#manual-patch-cancel");
  const executeButton = panel.querySelector("#manual-patch-execute");

  function requestJson(url, options = {}) {
    return fetch(url, options).then(async (response) => {
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `요청 실패 (${response.status})`);
      return payload;
    });
  }

  function uniqueLines(text) {
    return Array.from(new Set(String(text || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean)));
  }

  function parseEnvelope() {
    const text = String(envelopeNode.textContent || "").trim();
    if (!text || text === "Result Envelope 없음") return null;
    try {
      const value = JSON.parse(text);
      return value && typeof value === "object" ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function fileChanges(envelope) {
    return (Array.isArray(envelope?.artifacts) ? envelope.artifacts : [])
      .filter((item) => item && item.kind === "file_change")
      .filter((item) => ["create", "replace"].includes(String(item.action || "").toLowerCase()))
      .filter((item) => typeof item.path === "string" && typeof item.content === "string")
      .map((item) => ({
        action: String(item.action).toLowerCase(),
        path: item.path.trim(),
        content: item.content,
      }));
  }

  function renderFiles(items, previewItems = null) {
    files.replaceChildren();
    items.forEach((item, index) => {
      const preview = Array.isArray(previewItems) ? previewItems[index] : null;
      const li = document.createElement("li");
      const size = preview?.characters ?? item.content.length;
      li.textContent = `${item.action === "create" ? "생성" : "교체"} · ${item.path} · ${size.toLocaleString()}자`;
      files.appendChild(li);
    });
  }

  function clearPreview(message = "") {
    state.preview = null;
    cancelButton.hidden = true;
    executeButton.hidden = true;
    previewButton.hidden = false;
    badge.textContent = "검토 전";
    badge.dataset.route = "write";
    status.textContent = message;
  }

  function refreshFromEnvelope() {
    const envelope = parseEnvelope();
    const operations = fileChanges(envelope);
    state.envelope = envelope;
    state.operations = operations;
    if (!operations.length) {
      panel.hidden = true;
      clearPreview();
      return;
    }
    panel.hidden = false;
    summary.textContent = `${operations.length}개 파일 변경안입니다. 검토 전에는 로컬 파일을 건드리지 않습니다.`;
    scopes.value = operations.map((item) => item.path).join("\n");
    const commands = Array.isArray(envelope?.verification?.commands)
      ? envelope.verification.commands.filter((item) => typeof item === "string")
      : [];
    tests.value = commands.join("\n");
    renderFiles(operations);
    clearPreview("허용 범위와 검사 명령을 확인한 뒤 변경 검토를 누르세요.");
  }

  async function previewPatch() {
    if (!state.operations.length) {
      status.textContent = "적용 가능한 파일 변경안이 없습니다.";
      return;
    }
    previewButton.disabled = true;
    status.textContent = "현재 파일 상태와 허용 범위를 검사하고 있습니다.";
    try {
      const preview = await requestJson("/api/manual-patches/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request: requestField.value.trim(),
          allowed_write_paths: uniqueLines(scopes.value),
          operations: state.operations,
          test_commands: uniqueLines(tests.value),
        }),
      });
      state.preview = preview;
      renderFiles(state.operations, preview.operations_preview);
      badge.textContent = "승인 대기";
      previewButton.hidden = true;
      cancelButton.hidden = false;
      executeButton.hidden = false;
      status.textContent = "검토가 끝났습니다. 아래 적용 버튼을 누르기 전에는 파일이 바뀌지 않습니다.";
    } catch (error) {
      status.textContent = error.message;
    } finally {
      previewButton.disabled = false;
    }
  }

  async function cancelPatch() {
    if (!state.preview?.patch_id) return;
    cancelButton.disabled = true;
    try {
      await requestJson(`/api/manual-patches/${encodeURIComponent(state.preview.patch_id)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      clearPreview("파일 변경을 취소했습니다.");
      renderFiles(state.operations);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      cancelButton.disabled = false;
    }
  }

  async function executePatch() {
    if (!state.preview?.patch_id) return;
    executeButton.disabled = true;
    cancelButton.disabled = true;
    status.textContent = "파일을 적용하고 검사를 실행하고 있습니다.";
    try {
      const result = await requestJson(`/api/manual-patches/${encodeURIComponent(state.preview.patch_id)}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const completed = result.status === "completed";
      badge.textContent = completed ? "적용 완료" : result.status === "rolled_back" ? "원상복구" : "확인 필요";
      cancelButton.hidden = true;
      executeButton.hidden = true;
      previewButton.hidden = true;
      status.textContent = completed
        ? "검사까지 통과해 변경을 적용했습니다."
        : result.rollback?.restored
          ? `검사에 실패해 모든 변경을 원상복구했습니다. ${result.error || ""}`
          : `원상복구를 완전히 마치지 못했습니다. ${result.error || ""}`;
      const changes = result.receipt?.actual_changes || result.rollback?.reverted_changes || {};
      const changedPaths = [...(changes.created || []), ...(changes.modified || [])];
      showCompleted({
        run_id: result.patch_id,
        route: "MANUAL CHATGPT · FILE PATCH",
        execution_status: result.status,
        result_markdown: completed
          ? `## 파일 변경 완료\n\n${changedPaths.length}개 파일을 적용하고 허용된 검사를 통과했습니다.`
          : `## 파일 변경 원상복구\n\n검사 또는 적용 과정에서 문제가 발생해 변경을 되돌렸습니다.\n\n${result.error || "오류 내용을 확인해 주세요."}`,
        artifacts: changedPaths.map((path) => ({ path, action: completed ? "applied" : "reverted" })),
        evidence: (result.receipt?.tests || result.rollback?.tests || []).map((item) => ({
          source: item.command,
          finding: `종료 코드 ${item.returncode}`,
        })),
        limitations: result.error ? [result.error] : [],
        workspace_receipt: result.receipt || null,
        workspace_rollback: result.rollback || null,
      });
    } catch (error) {
      status.textContent = error.message;
      executeButton.disabled = false;
      cancelButton.disabled = false;
    }
  }

  importButton.addEventListener("click", () => window.setTimeout(refreshFromEnvelope, 0));
  requestField.addEventListener("input", () => {
    panel.hidden = true;
    state.envelope = null;
    state.operations = [];
    clearPreview();
  });
  previewButton.addEventListener("click", previewPatch);
  cancelButton.addEventListener("click", cancelPatch);
  executeButton.addEventListener("click", executePatch);

  new MutationObserver(() => {
    if (!importedSection.hidden) refreshFromEnvelope();
  }).observe(envelopeNode, { childList: true, characterData: true, subtree: true });

  window.setTimeout(refreshFromEnvelope, 0);
  window.PSOSManualPatch = Object.freeze({
    version: 1,
    refresh: refreshFromEnvelope,
  });
})();
