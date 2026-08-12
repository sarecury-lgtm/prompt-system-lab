(() => {
  const completed = document.querySelector("#completed-result");
  const runIdNode = document.querySelector("#run-id");
  const panel = document.querySelector("#next-loop-panel");
  const candidatesNode = document.querySelector("#next-loop-candidates");
  if (!completed || !runIdNode || !panel || !candidatesNode) return;

  const details = document.createElement("section");
  details.id = "next-loop-candidate-details";
  details.className = "next-loop-candidate-details";
  details.hidden = true;
  candidatesNode.insertAdjacentElement("afterend", details);

  let currentRunId = null;
  let loadingRunId = null;

  const verificationLabels = {
    unverified: "미검증",
    partially_verified: "부분 검증",
    verified: "검증됨",
    blocked: "접근 차단",
  };

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function stringify(value) {
    if (value === true) return "예";
    if (value === false) return "아니오";
    if (value === null || value === undefined) return "확인되지 않음";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function render(payload) {
    clear(details);
    const working = payload.candidate_working_set;
    const candidates = Array.isArray(working?.candidates)
      ? working.candidates.filter((candidate) => candidate.status !== "excluded")
      : [];
    if (!candidates.length) {
      details.hidden = true;
      return;
    }

    const heading = document.createElement("div");
    heading.className = "next-loop-details-heading";
    const title = document.createElement("h4");
    title.textContent = "후보별 확인 내용";
    const unresolved = document.createElement("p");
    const missing = Array.isArray(working.unresolved_requirements)
      ? working.unresolved_requirements
      : [];
    unresolved.textContent = missing.length
      ? `아직 확인할 것: ${missing.join(" · ")}`
      : "남아 있는 미확인 조건이 없습니다.";
    heading.append(title, unresolved);
    details.appendChild(heading);

    const list = document.createElement("div");
    list.className = "next-loop-details-list";
    candidates.forEach((candidate) => {
      const card = document.createElement("article");
      card.className = "next-loop-detail-card";
      const head = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = `${candidate.id} · ${candidate.name}`;
      const verification = document.createElement("span");
      verification.className = `next-loop-verification ${candidate.verification_status}`;
      verification.textContent =
        verificationLabels[candidate.verification_status] || candidate.verification_status;
      head.append(name, verification);
      card.appendChild(head);

      const attributes = candidate.attributes && typeof candidate.attributes === "object"
        ? Object.entries(candidate.attributes)
        : [];
      if (attributes.length) {
        const grid = document.createElement("dl");
        grid.className = "next-loop-attribute-grid";
        attributes.slice(0, 12).forEach(([key, value]) => {
          const term = document.createElement("dt");
          term.textContent = key;
          const description = document.createElement("dd");
          description.textContent = stringify(value);
          grid.append(term, description);
        });
        card.appendChild(grid);
      } else {
        const empty = document.createElement("p");
        empty.className = "next-loop-detail-empty";
        empty.textContent = "아직 구조화된 속성이 없습니다.";
        card.appendChild(empty);
      }

      const notes = [];
      if (Array.isArray(candidate.strengths) && candidate.strengths.length) {
        notes.push(`강점: ${candidate.strengths.join(" · ")}`);
      }
      if (Array.isArray(candidate.risks) && candidate.risks.length) {
        notes.push(`위험: ${candidate.risks.join(" · ")}`);
      }
      notes.forEach((text) => {
        const note = document.createElement("p");
        note.className = "next-loop-detail-note";
        note.textContent = text;
        card.appendChild(note);
      });
      list.appendChild(card);
    });
    details.appendChild(list);
    details.hidden = false;
  }

  async function load(runId) {
    if (!runId || runId === currentRunId || runId === loadingRunId) return;
    loadingRunId = runId;
    try {
      const response = await fetch(`/api/next-loop/runs/${encodeURIComponent(runId)}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `요청 실패 (${response.status})`);
      if (loadingRunId !== runId) return;
      currentRunId = runId;
      render(payload);
    } catch (_error) {
      if (loadingRunId === runId) {
        currentRunId = null;
        details.hidden = true;
      }
    } finally {
      if (loadingRunId === runId) loadingRunId = null;
    }
  }

  function sync() {
    if (completed.hidden) return;
    const runId = runIdNode.textContent.trim();
    if (runId) load(runId);
  }

  new MutationObserver(() => {
    currentRunId = null;
    sync();
  }).observe(runIdNode, { childList: true, characterData: true, subtree: true });
  new MutationObserver(sync).observe(completed, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  sync();
})();
