(() => {
  const MAX_FILES = 4;
  const MAX_FILE_BYTES = 5 * 1024 * 1024;
  const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }

  function readDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error(`${file.name} 파일을 읽지 못했습니다.`));
      reader.readAsDataURL(file);
    });
  }

  async function uploadFiles(files) {
    const encoded = await Promise.all(
      files.map(async (file) => ({
        name: file.name || "pasted-image.png",
        type: file.type,
        data_url: await readDataUrl(file),
      })),
    );
    const response = await fetch("/api/attachments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files: encoded }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `첨부 실패 (${response.status})`);
    return Array.isArray(payload.attachments) ? payload.attachments : [];
  }

  function referenceBlock(attachments) {
    const lines = attachments.map((item) => `- ${item.name}: ${item.path}`);
    return [
      "[첨부 시각 자료]",
      ...lines,
      "위 경로의 이미지를 직접 확인해 분석하세요. 이미지가 없어도 다른 근거가 충분하면 경고만 남기고 가능한 결론은 계속 내리세요.",
    ].join("\n");
  }

  function createAttachmentControl({ form, textarea, compact = false }) {
    if (!form || !textarea || form.dataset.attachmentsReady === "true") return;
    form.dataset.attachmentsReady = "true";

    const state = {
      files: [],
      bypass: false,
      busy: false,
    };

    const panel = document.createElement("div");
    panel.className = `attachment-control${compact ? " compact" : ""}`;
    panel.innerHTML = `
      <input class="attachment-input" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden>
      <div class="attachment-dropzone" tabindex="0">
        <button class="attachment-button" type="button">차트·스크린샷 첨부</button>
        <span>붙여넣기 또는 드래그도 가능 · 최대 4장</span>
      </div>
      <ul class="attachment-list" hidden></ul>
      <p class="attachment-status" role="status" aria-live="polite"></p>
    `;
    textarea.insertAdjacentElement("afterend", panel);

    const input = panel.querySelector(".attachment-input");
    const button = panel.querySelector(".attachment-button");
    const dropzone = panel.querySelector(".attachment-dropzone");
    const list = panel.querySelector(".attachment-list");
    const status = panel.querySelector(".attachment-status");

    function render() {
      list.replaceChildren();
      list.hidden = !state.files.length;
      state.files.forEach((file, index) => {
        const item = document.createElement("li");
        const label = document.createElement("span");
        label.textContent = `${file.name || `image-${index + 1}`} · ${formatSize(file.size)}`;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "삭제";
        remove.addEventListener("click", () => {
          state.files.splice(index, 1);
          status.textContent = "";
          render();
        });
        item.append(label, remove);
        list.appendChild(item);
      });
    }

    function addFiles(incoming) {
      const files = Array.from(incoming || []);
      const accepted = [];
      for (const file of files) {
        if (!ALLOWED_TYPES.has(file.type)) {
          status.textContent = "PNG, JPG, WEBP 이미지만 첨부할 수 있습니다.";
          continue;
        }
        if (file.size > MAX_FILE_BYTES) {
          status.textContent = `${file.name || "이미지"}는 5MB를 넘습니다.`;
          continue;
        }
        accepted.push(file);
      }
      const remaining = MAX_FILES - state.files.length;
      state.files.push(...accepted.slice(0, Math.max(0, remaining)));
      if (accepted.length > remaining) status.textContent = "이미지는 최대 4장까지 첨부할 수 있습니다.";
      render();
    }

    button.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      addFiles(input.files);
      input.value = "";
    });
    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragging");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragging"));
    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
      addFiles(event.dataTransfer?.files);
    });
    textarea.addEventListener("paste", (event) => {
      const images = Array.from(event.clipboardData?.items || [])
        .filter((item) => item.kind === "file" && ALLOWED_TYPES.has(item.type))
        .map((item) => item.getAsFile())
        .filter(Boolean);
      if (!images.length) return;
      event.preventDefault();
      addFiles(images);
      status.textContent = "붙여넣은 이미지를 첨부했습니다.";
    });

    form.addEventListener(
      "submit",
      async (event) => {
        if (state.bypass) {
          state.bypass = false;
          return;
        }
        if (!state.files.length || state.busy) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        state.busy = true;
        button.disabled = true;
        status.textContent = "이미지를 안전하게 저장하고 있습니다.";
        try {
          const attachments = await uploadFiles(state.files);
          const block = referenceBlock(attachments);
          const nextValue = `${textarea.value.trim()}\n\n${block}`.trim();
          if (textarea.maxLength > 0 && nextValue.length > textarea.maxLength) {
            throw new Error("첨부 경로를 넣으면 입력 글자 수 제한을 넘습니다.");
          }
          textarea.value = nextValue;
          state.files = [];
          render();
          status.textContent = "이미지가 요청에 연결됐습니다.";
          state.bypass = true;
          form.requestSubmit();
        } catch (error) {
          status.textContent = error.message || "이미지를 첨부하지 못했습니다.";
        } finally {
          state.busy = false;
          button.disabled = false;
        }
      },
      true,
    );
  }

  function setupMain() {
    const form = document.querySelector("#request-form");
    const textarea = document.querySelector("#request");
    createAttachmentControl({ form, textarea });
  }

  function setupCorrection() {
    const form = document.querySelector("#next-loop-correction-form");
    const textarea = document.querySelector("#next-loop-correction");
    createAttachmentControl({ form, textarea, compact: true });
  }

  setupMain();
  setupCorrection();
  const observer = new MutationObserver(() => setupCorrection());
  observer.observe(document.body, { childList: true, subtree: true });

  window.PSOSAttachments = Object.freeze({
    maxFiles: MAX_FILES,
    allowedTypes: Array.from(ALLOWED_TYPES),
  });
})();
