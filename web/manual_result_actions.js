(() => {
  const $ = (selector) => document.querySelector(selector);
  let resultBody = "";
  let fullResult = "";

  async function copyText(text, fallbackElement = null) {
    const value = String(text || "").trim();
    if (!value) return false;
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_error) {
      let element = fallbackElement;
      let temporary = false;
      if (!element) {
        element = document.createElement("textarea");
        element.value = value;
        element.setAttribute("readonly", "");
        element.style.position = "fixed";
        element.style.opacity = "0";
        document.body.appendChild(element);
        temporary = true;
      }
      element.focus();
      element.select();
      const copied = document.execCommand("copy");
      if (temporary) element.remove();
      return copied;
    }
  }

  function setTemporaryLabel(button, text, duration = 1800) {
    const original = button.dataset.label || button.textContent;
    button.dataset.label = original;
    button.textContent = text;
    window.setTimeout(() => {
      button.textContent = button.dataset.label || original;
    }, duration);
  }

  function openChatGPT() {
    const opened = window.open("https://chatgpt.com/", "_blank");
    if (opened) opened.opener = null;
    return Boolean(opened);
  }

  function extractResultBody(markdown) {
    const text = String(markdown || "").trim();
    if (!text) return "";
    const resultMarker = text.match(/(?:^|\n)결과:\s*(?:\n|$)/);
    let body = resultMarker
      ? text.slice(resultMarker.index + resultMarker[0].length)
      : text;
    const limitationMarker = body.match(
      /\n(?:#{1,6}\s*)?남은 핵심 한계:\s*(?:\n|$)/,
    );
    if (limitationMarker) body = body.slice(0, limitationMarker.index);
    return body.trim() || text;
  }

  function selectedRoute(markdown) {
    const match = String(markdown || "").match(
      /선택한 해결 방식:\s*([A-Z]+)/,
    );
    return match ? match[1] : "";
  }

  function buildPromptExecutionText(prompt) {
    return [
      "아래 프롬프트를 지금부터 그대로 적용해라.",
      "프롬프트 자체를 평가하거나 요약하거나 수정하지 말고, 요구된 최종 결과를 작성하라.",
      "필요한 이미지나 입력이 아직 없다면 필요한 자료만 짧게 요청하라.",
      "",
      String(prompt || "").trim(),
    ].join("\n");
  }

  function enhanceResultPanel() {
    const panel = $("#result-panel");
    const result = $("#result");
    if (!panel || panel.classList.contains("hidden") || !result) return;

    const visibleText = result.textContent.trim();
    if (!visibleText) return;
    if (!fullResult || visibleText !== resultBody) fullResult = visibleText;
    resultBody = extractResultBody(fullResult);
    result.textContent = resultBody;
    $("#full-result").textContent = fullResult;
    $("#full-result-details").open = false;

    const isPrompt = selectedRoute(fullResult) === "PROMPT";
    $("#run-prompt").classList.toggle("hidden", !isPrompt);
    $("#copy-result").classList.toggle("primary", !isPrompt);
    $("#copy-result").classList.toggle("quiet", isPrompt);
    $("#result-copy-help").textContent = isPrompt
      ? "실행할 때는 ‘프롬프트 실행하기’를 누르세요. 경로 설명과 브리지 한계는 복사되지 않습니다."
      : "아래에는 시스템 설명을 뺀 실제 결과만 표시됩니다.";
    $("#result-detail").textContent = "실제 결과와 PSOS 전체 기록을 분리했습니다.";
  }

  function replaceSendButton() {
    const oldButton = $("#send-to-chatgpt");
    if (!oldButton) return;
    const button = oldButton.cloneNode(true);
    oldButton.replaceWith(button);
    button.addEventListener("click", async () => {
      const prompt = $("#prompt");
      const copied = await copyText(prompt.value, prompt);
      if (!copied) {
        $("#prompt-details").open = true;
        setTemporaryLabel(button, "복사 실패 · 아래 지시문을 직접 복사하세요");
        return;
      }
      const opened = openChatGPT();
      setTemporaryLabel(
        button,
        opened
          ? "복사됨 · ChatGPT에 붙여넣으세요"
          : "복사됨 · ChatGPT를 직접 여세요",
      );
    });
  }

  $("#copy-result")?.addEventListener("click", async () => {
    const button = $("#copy-result");
    const copied = await copyText(resultBody);
    setTemporaryLabel(button, copied ? "결과만 복사됨" : "복사 실패");
  });

  $("#copy-full-result")?.addEventListener("click", async () => {
    const button = $("#copy-full-result");
    const copied = await copyText(fullResult);
    setTemporaryLabel(button, copied ? "전체 기록 복사됨" : "복사 실패");
  });

  $("#run-prompt")?.addEventListener("click", async () => {
    const button = $("#run-prompt");
    const copied = await copyText(buildPromptExecutionText(resultBody));
    if (!copied) {
      setTemporaryLabel(button, "복사 실패");
      return;
    }
    const opened = openChatGPT();
    setTemporaryLabel(
      button,
      opened
        ? "복사됨 · 입력 자료를 첨부하세요"
        : "복사됨 · ChatGPT를 직접 여세요",
    );
  });

  replaceSendButton();
  const resultPanel = $("#result-panel");
  if (resultPanel) {
    new MutationObserver(enhanceResultPanel).observe(resultPanel, {
      attributes: true,
      attributeFilter: ["class"],
    });
  }
  enhanceResultPanel();
})();
