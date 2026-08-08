(() => {
  if (
    typeof elements === "undefined" ||
    !elements.completed ||
    !elements.resultContent ||
    typeof requestJson !== "function"
  ) return;

  const controller = window.PSOSManualController;
  const HOST_ID = "psos-result-refinement";
  let busy = false;

  function terminalSession(session) {
    return Boolean(session && ["completed", "partial", "blocked"].includes(session.status));
  }

  function currentRequest() {
    return String(elements.request?.value || "").trim();
  }

  function currentResult() {
    return String(elements.resultContent?.innerText || "").trim().slice(0, 20000);
  }

  function ensureHost() {
    let host = document.querySelector(`#${HOST_ID}`);
    const hasResult = !elements.completed.hidden && Boolean(currentResult());
    if (!hasResult) {
      if (host) host.hidden = true;
      return;
    }
    if (!host) {
      host = document.createElement("section");
      host.id = HOST_ID;
      host.className = "manual-controller-card manual-controller-refinement";
      host.innerHTML = `
        <div class="manual-controller-refinement-head">
          <div>
            <strong>이 결과가 방향과 안 맞나요?</strong>
            <p>처음부터 버리지 않고, 현재 결과를 기준으로 바꿀 이유와 다음 방향을 반영합니다.</p>
          </div>
          <button id="psos-result-refinement-open" type="button">이 결과 수정하기</button>
        </div>
        <div id="psos-result-refinement-form" class="manual-controller-refinement-form" hidden>
          <label class="field-label" for="psos-result-refinement-reason">
            <span>왜 바꾸려는지</span>
            <textarea id="psos-result-refinement-reason" rows="3" maxlength="8000" placeholder="예: 맛만 보고 너무 비싼 제품을 골랐다."></textarea>
          </label>
          <label class="field-label" for="psos-result-refinement-direction">
            <span>다음에는 어떤 방향으로 갈지</span>
            <textarea id="psos-result-refinement-direction" rows="4" maxlength="8000" placeholder="예: 가격도 같이 보고 가성비픽 1, 품질픽 1로 다시 골라 줘."></textarea>
          </label>
          <div class="manual-controller-refinement-actions">
            <span id="psos-result-refinement-status" role="status" aria-live="polite"></span>
            <div>
              <button id="psos-result-refinement-cancel" type="button" class="secondary-button">취소</button>
              <button id="psos-result-refinement-submit" type="button">이 방향으로 다시 진행</button>
            </div>
          </div>
        </div>
      `;
      elements.completed.appendChild(host);

      const open = host.querySelector("#psos-result-refinement-open");
      const form = host.querySelector("#psos-result-refinement-form");
      const reason = host.querySelector("#psos-result-refinement-reason");
      const direction = host.querySelector("#psos-result-refinement-direction");
      const cancel = host.querySelector("#psos-result-refinement-cancel");
      const submit = host.querySelector("#psos-result-refinement-submit");
      const status = host.querySelector("#psos-result-refinement-status");

      open.addEventListener("click", () => {
        form.hidden = false;
        open.hidden = true;
        status.textContent = "";
        reason.focus();
      });
      cancel.addEventListener("click", () => {
        form.hidden = true;
        open.hidden = false;
        status.textContent = "";
      });
      submit.addEventListener("click", async () => {
        if (busy) return;
        const reasonText = reason.value.trim();
        const directionText = direction.value.trim();
        if (!directionText) {
          direction.focus();
          status.textContent = "다음 방향을 적어 주세요.";
          return;
        }
        const request = currentRequest();
        const previousResult = currentResult();
        if (!request || !previousResult) {
          status.textContent = "원래 요청이나 현재 결과를 찾지 못했습니다.";
          return;
        }

        busy = true;
        submit.disabled = true;
        cancel.disabled = true;
        status.textContent = "현재 결과를 보존하고 다음 행동을 만들고 있습니다.";
        try {
          const session = controller?.getSession?.();
          if (controller && terminalSession(session)) {
            await requestJson(
              `/api/manual-controller/sessions/${encodeURIComponent(session.session_id)}/refine`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reason: reasonText, direction: directionText }),
              },
            );
            await controller.reload();
          } else if (controller) {
            document.querySelector("#manual-controller-reset")?.click();
            const toggle = document.querySelector("#chatgpt-manual-enabled");
            if (toggle && !toggle.checked) {
              toggle.checked = true;
              toggle.dispatchEvent(new Event("change", { bubbles: true }));
            }
            const panel = document.querySelector("#manual-controller-panel");
            const requestField = panel?.querySelector("#manual-controller-request");
            const contextField = panel?.querySelector("#manual-controller-context");
            if (!requestField || !contextField) throw new Error("Controller 입력 화면을 찾지 못했습니다.");
            requestField.value = request;
            contextField.value = [
              "[이전 결과]",
              previousResult,
              "",
              "[사용자 결과 피드백]",
              reasonText ? `이유: ${reasonText}` : "이유: 사용자가 결과 수정 방향을 직접 지정함",
              `다음 방향: ${directionText}`,
            ].join("\n");
            await controller.start();
          } else {
            throw new Error("수정 세션을 시작할 Controller를 찾지 못했습니다.");
          }
          reason.value = "";
          direction.value = "";
          form.hidden = true;
          open.hidden = false;
          status.textContent = "수정 방향을 반영했습니다.";
          document.querySelector("#manual-controller-panel")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        } catch (error) {
          status.textContent = error.message;
        } finally {
          busy = false;
          submit.disabled = false;
          cancel.disabled = false;
        }
      });
    }
    host.hidden = false;
  }

  new MutationObserver(() => ensureHost()).observe(elements.completed, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["hidden", "class"],
  });
  ensureHost();

  window.PSOSResultRefinement = Object.freeze({ version: 1, ensure: ensureHost });
})();
