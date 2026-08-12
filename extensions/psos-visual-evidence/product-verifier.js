(() => {
  if (window.__PSOS_PRODUCT_VERIFIER__) return;
  window.__PSOS_PRODUCT_VERIFIER__ = true;

  const NEGATIVE = [
    /현재\s*판매\s*중인\s*상품이\s*아닙니다/i,
    /판매가\s*종료된\s*상품/i,
    /판매\s*(?:중지|종료)된?\s*상품/i,
    /\b(?:sold\s*out|out\s*of\s*stock|no\s*longer\s*available)\b/i,
  ];
  const CHALLENGE = [
    /잠시만\s*기다리십시오/i,
    /사람인지\s*확인/i,
    /로봇이\s*아닙니다/i,
    /enable javascript and cookies to continue/i,
    /checking your browser/i,
  ];
  const PURCHASE = /바로\s*구매|구매하기|주문하기|장바구니|buy\s*now|add\s*to\s*cart|place\s*order/i;

  function clean(value, limit = 4000) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
  }

  function unique(values, maximum = 20) {
    return [...new Set(values.map((value) => clean(value, 500)).filter(Boolean))].slice(0, maximum);
  }

  function visibleText() {
    return clean(document.body?.innerText || "", 60000);
  }

  function visibleControls() {
    return [...document.querySelectorAll("button, a, input[type='button'], input[type='submit']")]
      .filter((node) => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          rect.width > 0 &&
          rect.height > 0 &&
          !node.disabled &&
          node.getAttribute("aria-disabled") !== "true"
        );
      })
      .map((node) => ({
        tag: node.tagName,
        text: clean(node.innerText || node.value || node.getAttribute("aria-label"), 200),
      }))
      .filter((item) => {
        if (!PURCHASE.test(item.text)) return false;
        return item.tag !== "A" || !/^장바구니$/i.test(item.text);
      })
      .map((item) => item.text);
  }

  function fieldLines(text, pattern, maximum = 12) {
    return unique(
      String(text || "")
        .split(/\n+/)
        .map((line) => clean(line, 500))
        .filter((line) => pattern.test(line)),
      maximum,
    );
  }

  function priceValues(text) {
    const meta = [
      ...document.querySelectorAll(
        "meta[property='product:price:amount'], meta[itemprop='price'], [itemprop='price'][content]",
      ),
    ].map((node) => node.content || node.getAttribute("content"));
    const matches = String(text || "").match(/(?:\d{1,3}(?:,\d{3})+|\d{3,})\s*원/g) || [];
    return unique([...meta.map((value) => `${value}원`), ...matches], 20);
  }

  function selectedOptions() {
    const selects = [...document.querySelectorAll("select")]
      .map((node) => node.selectedOptions?.[0]?.textContent)
      .filter(Boolean);
    const checked = [...document.querySelectorAll("input:checked")]
      .map((node) => {
        const label = node.labels?.[0]?.innerText;
        return label || node.value || node.getAttribute("aria-label");
      })
      .filter(Boolean);
    return unique([...selects, ...checked], 20);
  }

  async function sha256(value) {
    if (!crypto?.subtle) return null;
    const bytes = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  async function buildReceipt(expectedUrl) {
    const text = visibleText();
    const title = clean(
      document.querySelector("meta[property='og:title']")?.content ||
        document.querySelector("h1")?.innerText ||
        document.title,
      500,
    );
    const controls = unique(visibleControls(), 12);
    const decisiveText = `${title} ${text.slice(0, 12000)}`;
    const negative = NEGATIVE.map((pattern) => decisiveText.match(pattern)).find(Boolean);
    const soldOutControl = [...document.querySelectorAll("button:disabled, [role='button'][aria-disabled='true']")]
      .map((node) => clean(node.innerText || node.getAttribute("aria-label"), 200))
      .find((value) => /품절|판매\s*종료|판매\s*중지/i.test(value));
    const challenge = CHALLENGE.map((pattern) => `${document.title} ${text}`.match(pattern)).find(Boolean);
    let status = "unknown";
    let signal = "no decisive purchase control";
    if (negative || soldOutControl) {
      status = "sold_out";
      signal = negative?.[0] || soldOutControl;
    } else if (challenge || document.querySelector("iframe[src*='challenge'], [class*='turnstile']")) {
      status = "needs_user";
      signal = challenge?.[0] || "browser challenge";
    } else if (controls.length) {
      status = "available";
      signal = controls[0];
    }
    return {
      url: expectedUrl,
      final_url: location.href,
      status,
      checked_at: new Date().toISOString(),
      signal: clean(signal, 500),
      excerpt: clean(text, 4000),
      text_sha256: await sha256(text),
      fields: {
        title,
        prices: priceValues(text),
        shipping: fieldLines(document.body?.innerText, /배송|택배|무료배송|배송비/i),
        weights: fieldLines(document.body?.innerText, /\b\d+(?:\.\d+)?\s*(?:kg|g|킬로|그램)\b/i),
        selected_options: selectedOptions(),
        purchase_controls: controls,
      },
    };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "PSOS_VERIFY_PRODUCT_PAGE") return false;
    buildReceipt(String(message.expectedUrl || location.href))
      .then(sendResponse)
      .catch((error) =>
        sendResponse({
          url: String(message.expectedUrl || location.href),
          final_url: location.href,
          status: "error",
          checked_at: new Date().toISOString(),
          signal: "page_extraction_error",
          excerpt: clean(error?.message || error),
          fields: {},
        }),
      );
    return true;
  });
})();
