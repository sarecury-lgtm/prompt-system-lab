function visible(element) {
  if (!element) return false;
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
}

function findComposer() {
  const selectors = [
    "#prompt-textarea",
    "textarea[data-id='root']",
    "form textarea",
    "main [contenteditable='true']",
    "textarea",
  ];
  for (const selector of selectors) {
    const items = [...document.querySelectorAll(selector)].filter(visible);
    if (items.length) return items.at(-1);
  }
  return null;
}

function composerText(composer) {
  if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
    return composer.value.trim();
  }
  return (composer.innerText || composer.textContent || "").trim();
}

function insertPrompt(prompt) {
  if (typeof prompt !== "string" || !prompt.trim()) {
    throw new Error("삽입할 PSOS 지시문이 비어 있습니다.");
  }
  const composer = findComposer();
  if (!composer) throw new Error("ChatGPT 입력창을 찾지 못했습니다.");
  const existing = composerText(composer);
  if (existing && existing !== prompt.trim()) {
    throw new Error("ChatGPT 입력창에 작성 중인 내용이 있어 덮어쓰지 않았습니다. 입력창을 비운 뒤 다시 시도하세요.");
  }
  composer.focus();
  if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
    const prototype = composer instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    setter?.call(composer, prompt);
    if (!setter) composer.value = prompt;
  } else {
    const paragraph = document.createElement("p");
    paragraph.textContent = prompt;
    composer.replaceChildren(paragraph);
  }
  composer.dispatchEvent(new InputEvent("input", {
    bubbles: true,
    inputType: "insertText",
    data: prompt,
  }));
  composer.dispatchEvent(new Event("change", { bubbles: true }));
  composer.scrollIntoView({ behavior: "smooth", block: "center" });
}

function responseText(container) {
  const content =
    container.querySelector(".markdown") ||
    container.querySelector("[data-message-content]") ||
    container;
  return content.innerText?.trim() || "";
}

function responseIsStreaming() {
  const selectors = [
    "button[data-testid='stop-button']",
    "button[aria-label*='Stop']",
    "button[aria-label*='중지']",
  ];
  return selectors.some((selector) => [...document.querySelectorAll(selector)].some(visible));
}

function lastAssistantResponse() {
  if (responseIsStreaming()) {
    throw new Error("ChatGPT가 아직 답변을 생성 중입니다. 완료된 뒤 다시 반환하세요.");
  }
  const items = [
    ...document.querySelectorAll("[data-message-author-role='assistant']"),
  ].filter(visible);
  if (!items.length) {
    throw new Error("역할이 확인된 마지막 ChatGPT 답변을 찾지 못했습니다. 임의의 글을 대신 반환하지 않았습니다.");
  }
  const text = responseText(items.at(-1));
  if (!text) throw new Error("마지막 ChatGPT 답변이 비어 있습니다.");
  return text;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  try {
    if (message.type === "PSOS_INSERT_PROMPT") {
      insertPrompt(message.prompt);
      sendResponse({ ok: true });
      return;
    }
    if (message.type === "PSOS_EXTRACT_LAST_RESPONSE") {
      sendResponse({ ok: true, response: lastAssistantResponse() });
      return;
    }
  } catch (error) {
    sendResponse({ ok: false, error: error.message });
  }
});
