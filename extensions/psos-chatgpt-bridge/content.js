function visible(element) {
  if (!element) return false;
  const style = getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
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

function insertPrompt(prompt) {
  const composer = findComposer();
  if (!composer) throw new Error("ChatGPT 입력창을 찾지 못했습니다.");
  composer.focus();
  if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(
      composer instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
      "value",
    )?.set;
    setter?.call(composer, prompt);
    if (!setter) composer.value = prompt;
  } else {
    composer.textContent = prompt;
  }
  composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
  composer.dispatchEvent(new Event("change", { bubbles: true }));
  composer.scrollIntoView({ behavior: "smooth", block: "center" });
}

function lastAssistantResponse() {
  const selectors = [
    "[data-message-author-role='assistant']",
    "article [data-message-author-role='assistant']",
  ];
  for (const selector of selectors) {
    const items = [...document.querySelectorAll(selector)].filter(visible);
    if (items.length) {
      const text = items.at(-1).innerText?.trim();
      if (text) return text;
    }
  }
  const articles = [...document.querySelectorAll("main article")].filter(visible);
  for (const article of articles.reverse()) {
    const text = article.innerText?.trim();
    if (text) return text;
  }
  throw new Error("마지막 ChatGPT 답변을 찾지 못했습니다.");
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
