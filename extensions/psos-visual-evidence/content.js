(() => {
  if (window.__PSOS_VISUAL_COLLECTOR__) return;
  window.__PSOS_VISUAL_COLLECTOR__ = true;

  const MAX_VISIBLE_CANDIDATES = 120;
  const MAX_SELECTED = 24;
  let host = null;

  function cleanText(value, limit) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
  }

  function isHttpUrl(value) {
    try {
      const url = new URL(value, location.href);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch (_error) {
      return null;
    }
  }

  function nearbyText(image) {
    const container = image.closest(
      "figure, article, li, [class*='review'], [class*='Review'], [class*='product'], [class*='Product'], [class*='item'], [class*='Item'], div",
    );
    return cleanText(container?.innerText || image.parentElement?.innerText || "", 800);
  }

  function collectImages() {
    const bySource = new Map();
    [...document.images].forEach((image) => {
      const source = isHttpUrl(image.currentSrc || image.src);
      if (!source) return;
      const rect = image.getBoundingClientRect();
      const width = Math.round(image.naturalWidth || rect.width || 0);
      const height = Math.round(image.naturalHeight || rect.height || 0);
      if (width < 120 || height < 90 || width * height < 18000) return;
      const style = getComputedStyle(image);
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
        return;
      }
      const anchor = image.closest("a[href]");
      const candidate = {
        src: source,
        alt: cleanText(image.alt, 300),
        width,
        height,
        nearby_text: nearbyText(image),
        link_url: anchor ? isHttpUrl(anchor.href) : null,
        area: width * height,
      };
      const existing = bySource.get(source);
      if (!existing || candidate.area > existing.area) bySource.set(source, candidate);
    });
    return [...bySource.values()]
      .sort((left, right) => right.area - left.area)
      .slice(0, MAX_VISIBLE_CANDIDATES)
      .map(({ area: _area, ...item }) => item);
  }

  function closePicker() {
    host?.remove();
    host = null;
  }

  function createPicker(defaults) {
    closePicker();
    const images = collectImages();
    host = document.createElement("div");
    host.id = "psos-visual-evidence-host";
    host.style.position = "fixed";
    host.style.inset = "0";
    host.style.zIndex = "2147483647";
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; }
        .backdrop { position: fixed; inset: 0; background: rgba(20, 27, 23, .72); font-family: Inter, Pretendard, "Noto Sans KR", sans-serif; color: #17211b; }
        .sheet { position: absolute; inset: 24px; display: grid; grid-template-rows: auto auto minmax(0, 1fr) auto; overflow: hidden; border-radius: 14px; background: #f7f8f5; box-shadow: 0 24px 80px rgba(0,0,0,.35); }
        header { display: flex; justify-content: space-between; gap: 20px; padding: 18px 20px; border-bottom: 1px solid #d9ded8; background: white; }
        h1 { margin: 0 0 4px; font-size: 20px; }
        header p { margin: 0; color: #657168; font-size: 12px; }
        button, input, select { font: inherit; }
        button { cursor: pointer; }
        .close { width: 38px; height: 38px; border: 1px solid #d9ded8; border-radius: 9px; background: white; font-size: 20px; }
        .fields { display: grid; grid-template-columns: 1.2fr 1fr 180px auto; gap: 10px; padding: 14px 20px; border-bottom: 1px solid #d9ded8; background: #fbfcfa; }
        label { display: grid; gap: 5px; color: #657168; font-size: 11px; font-weight: 700; }
        input, select { min-width: 0; height: 40px; padding: 0 10px; border: 1px solid #bfc8c0; border-radius: 8px; background: white; color: #17211b; }
        .small-actions { display: flex; align-items: end; gap: 6px; }
        .small-actions button { height: 40px; padding: 0 11px; border: 1px solid #bfc8c0; border-radius: 8px; background: white; color: #657168; font-size: 11px; font-weight: 700; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; overflow: auto; padding: 14px 20px 24px; align-content: start; }
        .empty { grid-column: 1 / -1; padding: 40px; border: 1px dashed #bfc8c0; border-radius: 10px; color: #657168; text-align: center; }
        .card { position: relative; display: grid; grid-template-rows: 150px auto; overflow: hidden; border: 1px solid #d9ded8; border-radius: 10px; background: white; }
        .card.selected { border-color: #176b46; box-shadow: 0 0 0 2px rgba(23,107,70,.14); }
        .card img { width: 100%; height: 150px; object-fit: contain; background: #eef1ed; }
        .card-body { display: grid; gap: 5px; padding: 9px; }
        .card strong { font-size: 11px; line-height: 1.35; }
        .card span { color: #657168; font-size: 10px; }
        .check { position: absolute; top: 8px; right: 8px; display: grid; width: 28px; height: 28px; place-items: center; border: 1px solid rgba(255,255,255,.8); border-radius: 50%; background: rgba(23,33,27,.78); color: white; }
        .check input { width: 15px; height: 15px; accent-color: #176b46; }
        footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 20px; border-top: 1px solid #d9ded8; background: white; }
        .status { min-height: 20px; margin: 0; color: #657168; font-size: 12px; }
        .submit { min-width: 170px; height: 42px; padding: 0 16px; border: 0; border-radius: 8px; background: #176b46; color: white; font-weight: 750; }
        .submit:disabled { cursor: not-allowed; opacity: .55; }
        @media (max-width: 850px) {
          .sheet { inset: 8px; }
          .fields { grid-template-columns: 1fr 1fr; }
          .small-actions { align-items: center; }
        }
      </style>
      <div class="backdrop">
        <section class="sheet" role="dialog" aria-modal="true" aria-label="PSOS 사진 근거 수집">
          <header>
            <div>
              <h1>PSOS 사진 근거 수집</h1>
              <p>현재 페이지에서 실제로 보이는 이미지 중 필요한 것만 고릅니다. 선택은 최대 ${MAX_SELECTED}장입니다.</p>
            </div>
            <button class="close" type="button" aria-label="닫기">×</button>
          </header>
          <div class="fields">
            <label>PSOS 실행 ID<input id="run-id" placeholder="psos-..."></label>
            <label>후보명<input id="subject-label" placeholder="예: 후보 A 또는 상품명"></label>
            <label>사진 출처<select id="source-kind">
              <option value="unknown">미확인</option>
              <option value="seller">판매자 제공</option>
              <option value="buyer_review">구매자 후기</option>
              <option value="editorial">기사·편집 자료</option>
            </select></label>
            <div class="small-actions"><button id="select-all" type="button">앞에서 24장</button><button id="clear" type="button">해제</button></div>
          </div>
          <div class="grid" id="grid"></div>
          <footer>
            <p class="status" id="status">이미지 ${images.length}개를 찾았습니다.</p>
            <button class="submit" id="submit" type="button">선택한 사진 추가</button>
          </footer>
        </section>
      </div>
    `;
    document.documentElement.appendChild(host);

    root.querySelector("#run-id").value = cleanText(defaults?.runId, 120);
    root.querySelector("#subject-label").value = cleanText(defaults?.subjectLabel, 160);
    const sourceKind = root.querySelector("#source-kind");
    sourceKind.value = ["seller", "buyer_review", "editorial", "unknown"].includes(defaults?.sourceKind)
      ? defaults.sourceKind
      : "unknown";
    const grid = root.querySelector("#grid");
    const status = root.querySelector("#status");
    const submit = root.querySelector("#submit");

    function selectedIndexes() {
      return [...root.querySelectorAll(".card input:checked")].map((node) => Number(node.dataset.index));
    }

    function updateSelection() {
      root.querySelectorAll(".card").forEach((card) => {
        const checked = card.querySelector("input").checked;
        card.classList.toggle("selected", checked);
      });
      const count = selectedIndexes().length;
      status.textContent = `${images.length}개 중 ${count}개 선택`;
      submit.disabled = count === 0;
    }

    if (!images.length) {
      grid.innerHTML = '<p class="empty">조건에 맞는 이미지가 없습니다. 페이지를 조금 내려 사진을 불러온 뒤 다시 열어 보세요.</p>';
      submit.disabled = true;
    } else {
      images.forEach((item, index) => {
        const card = document.createElement("label");
        card.className = "card";
        const image = document.createElement("img");
        image.src = item.src;
        image.alt = item.alt || "수집 후보 이미지";
        const check = document.createElement("span");
        check.className = "check";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.dataset.index = String(index);
        input.addEventListener("change", () => {
          if (selectedIndexes().length > MAX_SELECTED) input.checked = false;
          updateSelection();
        });
        check.appendChild(input);
        const body = document.createElement("div");
        body.className = "card-body";
        const title = document.createElement("strong");
        title.textContent = item.alt || item.nearby_text || "설명 없는 이미지";
        const dimensions = document.createElement("span");
        dimensions.textContent = `${item.width} × ${item.height}`;
        body.append(title, dimensions);
        card.append(image, check, body);
        grid.appendChild(card);
      });
    }

    root.querySelector(".close").addEventListener("click", closePicker);
    root.querySelector("#select-all").addEventListener("click", () => {
      root.querySelectorAll(".card input").forEach((input, index) => {
        input.checked = index < MAX_SELECTED;
      });
      updateSelection();
    });
    root.querySelector("#clear").addEventListener("click", () => {
      root.querySelectorAll(".card input").forEach((input) => {
        input.checked = false;
      });
      updateSelection();
    });
    submit.addEventListener("click", async () => {
      const runId = cleanText(root.querySelector("#run-id").value, 120);
      const subjectLabel = cleanText(root.querySelector("#subject-label").value, 160);
      const indexes = selectedIndexes();
      if (!runId || !subjectLabel || !indexes.length) {
        status.textContent = "실행 ID, 후보명, 사진 선택이 모두 필요합니다.";
        return;
      }
      submit.disabled = true;
      status.textContent = "PSOS에 추가하고 있습니다.";
      const response = await chrome.runtime.sendMessage({
        type: "PSOS_IMPORT_VISUAL_EVIDENCE",
        runId,
        payload: {
          subject_label: subjectLabel,
          source_kind: sourceKind.value,
          page_url: location.href,
          page_title: cleanText(document.title, 300),
          captured_at: new Date().toISOString(),
          images: indexes.map((index) => images[index]),
        },
      });
      if (!response?.ok) {
        status.textContent = response?.error || "PSOS에 사진을 추가하지 못했습니다.";
        submit.disabled = false;
        return;
      }
      status.textContent = `${response.subjectLabel}에 사진 ${response.added}장을 추가했습니다. PSOS 화면을 새로고침하세요.`;
    });

    updateSelection();
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "PSOS_VISUAL_PICKER_OPEN") {
      createPicker(message.defaults || {});
    }
  });
})();
