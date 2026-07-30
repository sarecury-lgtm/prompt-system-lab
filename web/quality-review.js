(() => {
  const completed = document.querySelector("#completed-result");
  const evidencePanel = document.querySelector("#evidence-panel");
  const runIdNode = document.querySelector("#run-id");
  if (!completed || !evidencePanel || !runIdNode) return;

  const labels = {
    keep: "유지",
    question: "의심",
    exclude: "제외",
    unreviewed: "미검토",
  };
  const kindLabels = {
    result_text: "최종 결과",
    web: "웹",
    local: "로컬 자료",
    command_output: "실행 출력",
    provided_context: "제공 문맥",
    image: "이미지",
    artifact: "산출물",
    receipt: "검증 기록",
  };

  const panel = document.createElement("section");
  panel.id = "quality-evidence-review";
  panel.className = "quality-review";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="quality-review-heading">
      <div>
        <span class="quality-kicker">근거 직접 검토</span>
        <h3>AI와 같은 원본을 보고 판정합니다.</h3>
        <p>사진·링크·파일을 확인한 뒤 유지, 의심, 제외를 표시하세요.</p>
      </div>
      <span id="quality-review-state" class="quality-state">불러오는 중</span>
    </div>
    <div id="quality-requirements" class="quality-requirements"></div>
    <div class="quality-toolbar" aria-label="근거 필터">
      <button type="button" data-filter="all" aria-pressed="true">전체</button>
      <button type="button" data-filter="image" aria-pressed="false">사진</button>
      <button type="button" data-filter="web" aria-pressed="false">링크</button>
      <button type="button" data-filter="file" aria-pressed="false">파일·실행</button>
    </div>
    <div id="quality-gallery" class="quality-gallery"></div>
    <label class="quality-overall-note">
      <span>전체 메모</span>
      <textarea id="quality-reviewer-note" rows="3" maxlength="2000" placeholder="예: 2번 사진은 다른 옵션처럼 보임. 이 근거 없이 다시 비교할 것."></textarea>
    </label>
    <label class="quality-search-control">
      <input id="quality-revision-search" type="checkbox">
      <span>의심한 웹 근거를 수정할 때 다시 검색 허용</span>
    </label>
    <div class="quality-actions">
      <p id="quality-message" role="status" aria-live="polite"></p>
      <div>
        <button id="quality-save-review" type="button" class="quality-secondary">판정 저장</button>
        <button id="quality-start-revision" type="button" class="quality-primary" disabled>판정 반영해 결과 수정</button>
      </div>
    </div>
  `;
  evidencePanel.insertAdjacentElement("afterend", panel);

  const stateNode = panel.querySelector("#quality-review-state");
  const requirementsNode = panel.querySelector("#quality-requirements");
  const gallery = panel.querySelector("#quality-gallery");
  const reviewerNote = panel.querySelector("#quality-reviewer-note");
  const searchToggle = panel.querySelector("#quality-revision-search");
  const message = panel.querySelector("#quality-message");
  const saveButton = panel.querySelector("#quality-save-review");
  const revisionButton = panel.querySelector("#quality-start-revision");
  const filterButtons = [...panel.querySelectorAll("[data-filter]")];

  let currentRunId = null;
  let bundleSha = null;
  let bundle = null;
  let review = null;
  let activeFilter = "all";
  let loadingRunId = null;

  function qClear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  async function qRequestJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `요청 실패 (${response.status})`);
    return payload;
  }

  function decisionMap() {
    return new Map((review?.decisions || []).map((item) => [item.evidence_id, item]));
  }

  function actionableCount() {
    return (review?.decisions || []).filter((item) =>
      ["question", "exclude"].includes(item.decision),
    ).length;
  }

  function updateActionState() {
    const reviewed = (review?.decisions || []).filter((item) => item.decision !== "unreviewed").length;
    const total = review?.decisions?.length || 0;
    stateNode.textContent = `${reviewed} / ${total} 검토`;
    revisionButton.disabled = actionableCount() === 0;
  }

  function setDecision(evidenceId, decision) {
    const target = review.decisions.find((item) => item.evidence_id === evidenceId);
    if (!target) return;
    target.decision = decision;
    panel.querySelectorAll(`[data-evidence-id="${CSS.escape(evidenceId)}"] [data-decision]`).forEach((button) => {
      const selected = button.dataset.decision === decision;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("selected", selected);
    });
    updateActionState();
    message.textContent = "저장되지 않은 판정이 있습니다.";
  }

  function category(item) {
    if (item.kind === "image") return "image";
    if (item.kind === "web") return "web";
    return "file";
  }

  function renderRequirements() {
    qClear(requirementsNode);
    (bundle?.requirements || []).forEach((requirement) => {
      const item = document.createElement("span");
      item.className = `quality-requirement ${requirement.status}`;
      item.textContent = `${requirement.status === "satisfied" ? "확인" : "주의"} · ${requirement.description}`;
      item.title = requirement.id;
      requirementsNode.appendChild(item);
    });
  }

  function linkedRequirements(evidenceId) {
    return (bundle?.requirements || [])
      .filter((item) => (item.evidence_item_ids || []).includes(evidenceId))
      .map((item) => item.description);
  }

  function renderCard(item, savedDecision) {
    const card = document.createElement("article");
    card.className = "quality-card";
    card.dataset.category = category(item);
    card.dataset.evidenceId = item.id;

    if (item.preview_url) {
      const media = document.createElement("div");
      media.className = "quality-media";
      const image = document.createElement("img");
      image.loading = "lazy";
      image.alt = item.finding || `${item.id} 근거 이미지`;
      image.src = item.preview_url;
      const fallback = document.createElement("p");
      fallback.hidden = true;
      fallback.textContent = "미리보기를 불러오지 못했습니다. 원본 링크를 확인하세요.";
      image.addEventListener("error", () => {
        image.hidden = true;
        fallback.hidden = false;
      });
      media.append(image, fallback);
      card.appendChild(media);
    }

    const body = document.createElement("div");
    body.className = "quality-card-body";
    const meta = document.createElement("div");
    meta.className = "quality-card-meta";
    const kind = document.createElement("span");
    kind.textContent = kindLabels[item.kind] || item.kind;
    const id = document.createElement("code");
    id.textContent = item.id;
    meta.append(kind, id);

    const finding = document.createElement("p");
    finding.className = "quality-finding";
    finding.textContent = item.finding;

    const sourceRow = document.createElement("div");
    sourceRow.className = "quality-source";
    if (item.open_url) {
      const link = document.createElement("a");
      link.href = item.open_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "원본 열기 ↗";
      sourceRow.appendChild(link);
    } else {
      const source = document.createElement("code");
      source.textContent = item.source;
      sourceRow.appendChild(source);
    }

    const connections = linkedRequirements(item.id);
    if (connections.length) {
      const connectionList = document.createElement("ul");
      connectionList.className = "quality-connections";
      connections.forEach((text) => {
        const node = document.createElement("li");
        node.textContent = text;
        connectionList.appendChild(node);
      });
      body.append(meta, finding, sourceRow, connectionList);
    } else {
      body.append(meta, finding, sourceRow);
    }

    const controls = document.createElement("div");
    controls.className = "quality-decision-group";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", `${item.id} 판정`);
    ["keep", "question", "exclude"].forEach((decision) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.decision = decision;
      button.textContent = labels[decision];
      const selected = savedDecision?.decision === decision;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("selected", selected);
      button.addEventListener("click", () => setDecision(item.id, decision));
      controls.appendChild(button);
    });

    const note = document.createElement("textarea");
    note.rows = 2;
    note.maxLength = 500;
    note.placeholder = "이 판정의 이유나 다시 볼 점";
    note.value = savedDecision?.note || "";
    note.addEventListener("input", () => {
      const target = review.decisions.find((entry) => entry.evidence_id === item.id);
      if (target) target.note = note.value;
      message.textContent = "저장되지 않은 메모가 있습니다.";
    });

    body.append(controls, note);
    card.appendChild(body);
    return card;
  }

  function applyFilter() {
    gallery.querySelectorAll(".quality-card").forEach((card) => {
      card.hidden = activeFilter !== "all" && card.dataset.category !== activeFilter;
    });
    filterButtons.forEach((button) => {
      const selected = button.dataset.filter === activeFilter;
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function renderGallery() {
    qClear(gallery);
    const decisions = decisionMap();
    const items = (bundle?.items || []).filter((item) => item.reviewable);
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "quality-empty";
      empty.textContent = "직접 검토할 수 있는 근거가 없습니다.";
      gallery.appendChild(empty);
      return;
    }
    items.forEach((item) => gallery.appendChild(renderCard(item, decisions.get(item.id))));
    applyFilter();
  }

  function collectPayload() {
    return {
      bundle_sha256: bundleSha,
      reviewer_note: reviewerNote.value,
      search_enabled: searchToggle.checked,
      decisions: review.decisions.map((item) => ({
        evidence_id: item.evidence_id,
        decision: item.decision,
        note: item.note || "",
      })),
    };
  }

  async function loadReview(runId) {
    loadingRunId = runId;
    panel.hidden = false;
    panel.classList.add("loading");
    stateNode.textContent = "근거 불러오는 중";
    message.textContent = "";
    try {
      const payload = await qRequestJson(`/api/runs/${encodeURIComponent(runId)}/evidence-review`);
      if (loadingRunId !== runId) return;
      currentRunId = runId;
      bundleSha = payload.bundle_sha256;
      bundle = payload.bundle;
      review = payload.review;
      reviewerNote.value = review.reviewer_note || "";
      renderRequirements();
      renderGallery();
      updateActionState();
      panel.hidden = false;
    } catch (error) {
      if (loadingRunId !== runId) return;
      panel.hidden = true;
      if (!String(error.message).includes("찾을 수 없습니다")) {
        console.warn("Evidence review unavailable:", error);
      }
    } finally {
      panel.classList.remove("loading");
    }
  }

  async function saveReview() {
    if (!currentRunId || !bundleSha) return null;
    saveButton.disabled = true;
    revisionButton.disabled = true;
    message.textContent = "판정을 저장하고 있습니다.";
    try {
      const payload = await qRequestJson(
        `/api/runs/${encodeURIComponent(currentRunId)}/evidence-review`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectPayload()),
        },
      );
      review = payload.review;
      message.textContent = "판정을 저장했습니다.";
      updateActionState();
      return payload;
    } catch (error) {
      message.textContent = error.message;
      throw error;
    } finally {
      saveButton.disabled = false;
      updateActionState();
    }
  }

  async function startRevision() {
    if (!currentRunId || actionableCount() === 0) return;
    saveButton.disabled = true;
    revisionButton.disabled = true;
    message.textContent = "원본을 보존한 새 수정 실행을 만들고 있습니다.";
    try {
      const payload = await qRequestJson(
        `/api/runs/${encodeURIComponent(currentRunId)}/evidence-revision`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectPayload()),
        },
      );
      window.sessionStorage.setItem("psos-active-job", payload.job.job_id);
      window.location.assign("/");
    } catch (error) {
      message.textContent = error.message;
      saveButton.disabled = false;
      updateActionState();
    }
  }

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.filter;
      applyFilter();
    });
  });
  saveButton.addEventListener("click", () => saveReview().catch(() => {}));
  revisionButton.addEventListener("click", startRevision);

  function syncRun() {
    const runId = runIdNode.textContent.trim();
    if (completed.hidden || !runId) return;
    if (runId !== currentRunId && runId !== loadingRunId) loadReview(runId);
  }

  new MutationObserver(syncRun).observe(completed, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  new MutationObserver(syncRun).observe(runIdNode, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  syncRun();
})();
