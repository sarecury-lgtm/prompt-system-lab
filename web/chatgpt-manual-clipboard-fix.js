(() => {
  const openButton = document.querySelector("#chatgpt-manual-open");
  const copyButton = document.querySelector("#chatgpt-manual-copy");
  const packet = document.querySelector("#chatgpt-manual-packet");
  const status = document.querySelector("#chatgpt-manual-status");
  const details = document.querySelector(".manual-v4-packet-details");

  if (!openButton || !copyButton || !packet || !status) return;

  function synchronousCopy(text) {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.setAttribute("aria-hidden", "true");
    helper.style.position = "fixed";
    helper.style.left = "-9999px";
    helper.style.top = "0";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.focus();
    helper.select();
    helper.setSelectionRange(0, helper.value.length);

    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (_error) {
      copied = false;
    }
    helper.remove();
    return copied;
  }

  function showManualCopy() {
    if (details) details.open = true;
    packet.focus();
    packet.select();
    status.textContent = "자동 복사에 실패했습니다. 선택된 내용을 Ctrl+C로 복사해 주세요.";
  }

  function copyWithFallback(text, onSuccess) {
    if (synchronousCopy(text)) {
      onSuccess();
      return;
    }

    if (!navigator.clipboard?.writeText) {
      showManualCopy();
      return;
    }

    navigator.clipboard.writeText(text).then(onSuccess).catch(showManualCopy);
  }

  openButton.addEventListener(
    "click",
    (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const text = packet.value.trim();
      if (!text) {
        status.textContent = "먼저 질문을 입력해 주세요.";
        return;
      }

      openButton.disabled = true;
      status.textContent = "보낼 내용을 복사하고 있습니다.";
      copyWithFallback(packet.value, () => {
        status.textContent = "복사 완료. ChatGPT를 엽니다.";
        const opened = window.open(
          "https://chatgpt.com/",
          "_blank",
          "noopener,noreferrer",
        );
        if (!opened) {
          status.textContent = "복사는 완료했습니다. 팝업이 차단되어 ChatGPT를 직접 열어 주세요.";
        }
        openButton.disabled = false;
      });
    },
    true,
  );

  copyButton.addEventListener(
    "click",
    (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const text = packet.value.trim();
      if (!text) {
        status.textContent = "먼저 질문을 입력해 주세요.";
        return;
      }
      copyWithFallback(packet.value, () => {
        status.textContent = "보낼 내용을 복사했습니다.";
      });
    },
    true,
  );

  window.PSOSManualClipboardFix = Object.freeze({ version: 1 });
})();
