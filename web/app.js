const elements = {
  form: document.querySelector("#request-form"),
  request: document.querySelector("#request"),
  search: document.querySelector("#search-enabled"),
  submit: document.querySelector("#submit-button"),
  empty: document.querySelector("#empty-result"),
  running: document.querySelector("#running-result"),
  runningTitle: document.querySelector("#running-title"),
  runningDetail: document.querySelector("#running-detail"),
  completed: document.querySelector("#completed-result"),
  error: document.querySelector("#error-result"),
  errorMessage: document.querySelector("#error-message"),
  resultContent: document.querySelector("#result-content"),
  resultMeta: document.querySelector("#result-meta"),
  route: document.querySelector("#route-badge"),
  runId: document.querySelector("#run-id"),
  evidenceList: document.querySelector("#evidence-list"),
  artifactList: document.querySelector("#artifact-list"),
  evidencePanel: document.querySelector("#evidence-panel"),
  headerStatus: document.querySelector("#header-status"),
  healthValue: document.querySelector("#health-value"),
  healthDescription: document.querySelector("#health-description"),
  validRuns: document.querySelector("#valid-runs"),
  completedRuns: document.querySelector("#completed-runs"),
  learningEvents: document.querySelector("#learning-events"),
  unreviewedEvents: document.querySelector("#unreviewed-events"),
  nextActionValue: document.querySelector("#next-action-value"),
  nextActionDescription: document.querySelector("#next-action-description"),
  recentRuns: document.querySelector("#recent-run-list"),
  refreshStatus: document.querySelector("#refresh-status"),
};

const nextActionCopy = {
  inspect_invalid_records: ["손상 기록 확인", "무효 기록이나 정책 드리프트의 원인을 먼저 확인하세요."],
  review_learning_candidates: ["학습 후보 검토", "실제 결과가 유용했는지 확인한 뒤 승격 또는 거절하세요."],
  collect_more_real_outcomes: ["실제 요청 더 사용", "검증된 결과를 더 모아야 정책 개선을 판단할 수 있습니다."],
  check_policy_proposal_eligibility: ["정책 제안 가능성 확인", "독립적인 승격 근거가 충분한지 확인하세요."],
  run_paired_policy_evaluation: ["기존 정책과 비교 평가", "후보 정책이 실제로 더 나은지 같은 조건에서 비교하세요."],
  approve_passed_policy_evaluation: ["통과한 변경 승인", "평가 근거를 사람이 검토해야 합니다."],
  apply_or_defer_approved_policy: ["정책 적용 여부 결정", "승인된 변경을 적용하거나 보류하세요."],
  resume_interrupted_policy_change: ["중단된 변경 재개", "검증된 receipt를 기준으로 안전하게 재개할 수 있습니다."],
  monitor_applied_policy: ["적용 정책 관찰", "새 정책의 실제 결과와 부작용을 계속 확인하세요."],
  continue_normal_operation: ["정상 사용 계속", "현재 특별히 처리해야 할 문제가 없습니다."],
};

let activeJobId = null;
let pollTimer = null;
const activeJobStorageKey = "psos-active-job";

function setResultState(state) {
  elements.empty.hidden = state !== "empty";
  elements.running.hidden = state !== "running";
  elements.completed.hidden = state !== "completed";
  elements.error.hidden = state !== "error";
  elements.resultMeta.hidden = !["completed"].includes(state);
}

function clearElement(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function appendTextItem(list, text, fallback) {
  const item = document.createElement("li");
  item.textContent = text || fallback;
  list.appendChild(item);
}

function inlineCode(container, text) {
  const fragments = text.split(/(`[^`]+`)/g);
  fragments.forEach((fragment) => {
    if (fragment.startsWith("`") && fragment.endsWith("`")) {
      const code = document.createElement("code");
      code.textContent = fragment.slice(1, -1);
      container.appendChild(code);
    } else {
      container.appendChild(document.createTextNode(fragment));
    }
  });
}

function renderMarkdown(markdown) {
  clearElement(elements.resultContent);
  const lines = String(markdown || "").replace(/\r/g, "").split("\n");
  let list = null;
  let code = null;
  let paragraph = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const node = document.createElement("p");
    inlineCode(node, paragraph.join(" "));
    elements.resultContent.appendChild(node);
    paragraph = [];
  };

  const closeList = () => {
    list = null;
  };

  lines.forEach((line) => {
    if (line.startsWith("```")) {
      flushParagraph();
      closeList();
      if (code) {
        code = null;
      } else {
        const pre = document.createElement("pre");
        code = document.createElement("code");
        pre.appendChild(code);
        elements.resultContent.appendChild(pre);
      }
      return;
    }
    if (code) {
      code.textContent += `${line}\n`;
      return;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      closeList();
      const node = document.createElement(`h${heading[1].length}`);
      inlineCode(node, heading[2]);
      elements.resultContent.appendChild(node);
      return;
    }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      if (!list) {
        list = document.createElement("ul");
        elements.resultContent.appendChild(list);
      }
      const item = document.createElement("li");
      inlineCode(item, bullet[1]);
      list.appendChild(item);
      return;
    }
    if (!line.trim()) {
      flushParagraph();
      closeList();
      return;
    }
    closeList();
    paragraph.push(line.trim());
  });
  flushParagraph();
}

function renderEvidence(data) {
  clearElement(elements.evidenceList);
  clearElement(elements.artifactList);
  const evidence = Array.isArray(data.evidence) ? data.evidence : [];
  const artifacts = Array.isArray(data.artifacts) ? data.artifacts : [];
  if (!evidence.length) appendTextItem(elements.evidenceList, "", "기록된 근거가 없습니다.");
  evidence.forEach((item) => {
    const source = item.source ? `${item.source}: ` : "";
    appendTextItem(elements.evidenceList, `${source}${item.finding || "근거 확인"}`);
  });
  if (!artifacts.length) appendTextItem(elements.artifactList, "", "확인한 파일이 없습니다.");
  artifacts.forEach((item) => {
    const action = item.action ? ` · ${item.action}` : "";
    appendTextItem(elements.artifactList, `${item.path || "경로 없음"}${action}`);
  });
  elements.evidencePanel.open = false;
}

function showCompleted(data) {
  activeJobId = null;
  window.sessionStorage.removeItem(activeJobStorageKey);
  elements.submit.disabled = false;
  elements.route.textContent = data.route || "경로 없음";
  elements.runId.textContent = data.run_id || "";
  renderMarkdown(data.result_markdown);
  renderEvidence(data);
  setResultState("completed");
  elements.resultContent.focus?.();
}

function showError(message) {
  activeJobId = null;
  window.sessionStorage.removeItem(activeJobStorageKey);
  elements.submit.disabled = false;
  elements.errorMessage.textContent = message || "알 수 없는 오류가 발생했습니다.";
  setResultState("error");
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `요청 실패 (${response.status})`);
  return payload;
}

async function pollJob() {
  if (!activeJobId) return;
  try {
    const job = await requestJson(`/api/jobs/${activeJobId}`);
    if (job.state === "completed") {
      showCompleted(job);
      await loadStatus();
      return;
    }
    if (job.state === "failed") {
      showError(job.error);
      return;
    }
    elements.runningTitle.textContent =
      job.state === "queued" ? "실행 순서를 기다리고 있습니다." : "요청을 해결하고 있습니다.";
    elements.runningDetail.textContent =
      job.state === "queued"
        ? "앞선 요청이 끝나면 자동으로 시작합니다."
        : "모델 선택, 실행, 근거 검증 순서로 진행합니다.";
    pollTimer = window.setTimeout(pollJob, 1200);
  } catch (error) {
    showError(error.message);
  }
}

async function submitRequest(event) {
  event.preventDefault();
  const request = elements.request.value.trim();
  if (!request) {
    elements.request.focus();
    return;
  }
  window.clearTimeout(pollTimer);
  elements.submit.disabled = true;
  setResultState("running");
  elements.runningTitle.textContent = "요청을 접수하고 있습니다.";
  elements.runningDetail.textContent = "잠시만 기다려 주세요.";
  try {
    const job = await requestJson("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request,
        search_enabled: elements.search.checked,
      }),
    });
    activeJobId = job.job_id;
    window.sessionStorage.setItem(activeJobStorageKey, activeJobId);
    pollJob();
  } catch (error) {
    showError(error.message);
  }
}

function renderRecentRuns(items) {
  clearElement(elements.recentRuns);
  const runs = [...(items || [])]
    .sort((left, right) => String(right.finished_at || "").localeCompare(String(left.finished_at || "")))
    .slice(0, 6);
  if (!runs.length) {
    const empty = document.createElement("p");
    empty.className = "run-empty";
    empty.textContent = "아직 실행 기록이 없습니다.";
    elements.recentRuns.appendChild(empty);
    return;
  }
  runs.forEach((run) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run-button";
    button.dataset.runId = run.run_id;
    const id = document.createElement("strong");
    id.textContent = run.run_id;
    const state = document.createElement("span");
    state.className = run.valid ? "run-valid" : "run-invalid";
    state.textContent = run.valid ? "유효" : "확인 필요";
    const route = document.createElement("span");
    route.textContent = run.execution_status || "상태 없음";
    button.append(id, state, route);
    button.addEventListener("click", () => loadRun(run.run_id, button));
    elements.recentRuns.appendChild(button);
  });
}

async function loadRun(runId, button = null) {
  try {
    const data = await requestJson(`/api/runs/${encodeURIComponent(runId)}`);
    document.querySelectorAll(".run-button").forEach((node) => {
      node.removeAttribute("aria-current");
    });
    if (button) button.setAttribute("aria-current", "true");
    showCompleted(data);
    const url = new URL(window.location.href);
    url.searchParams.set("run", runId);
    window.history.replaceState({}, "", url);
    if (button) document.querySelector("#result-heading").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    showError(error.message);
  }
}

async function loadStatus() {
  elements.refreshStatus.disabled = true;
  try {
    const status = await requestJson("/api/status");
    const runs = status.summary.runs;
    const healthy = status.status === "healthy";
    elements.headerStatus.className = `system-state ${status.status}`;
    elements.headerStatus.querySelector("span:last-child").textContent =
      healthy ? "시스템 정상" : "확인 필요";
    elements.healthValue.textContent = healthy ? "정상" : "확인 필요";
    elements.healthDescription.textContent = healthy
      ? "저장된 기록의 무결성 문제가 없습니다."
      : `${status.summary.invalid_count}개의 기록을 확인해야 합니다.`;
    elements.validRuns.textContent = `${runs.valid} / ${runs.total}`;
    elements.completedRuns.textContent = String(runs.completed);
    elements.learningEvents.textContent = String(runs.learning_events);
    elements.unreviewedEvents.textContent = String(runs.unreviewed);
    const firstAction = status.next_actions[0] || "continue_normal_operation";
    const copy = nextActionCopy[firstAction] || [firstAction, ""];
    elements.nextActionValue.textContent = copy[0];
    elements.nextActionDescription.textContent = copy[1];
    renderRecentRuns(status.items.runs);
  } catch (error) {
    elements.headerStatus.className = "system-state attention";
    elements.headerStatus.querySelector("span:last-child").textContent = "상태 확인 실패";
    elements.healthValue.textContent = "연결 오류";
    elements.healthDescription.textContent = error.message;
  } finally {
    elements.refreshStatus.disabled = false;
  }
}

elements.form.addEventListener("submit", submitRequest);
elements.refreshStatus.addEventListener("click", loadStatus);
loadStatus();
const initialRun = new URL(window.location.href).searchParams.get("run");
const storedJob = window.sessionStorage.getItem(activeJobStorageKey);
if (storedJob) {
  activeJobId = storedJob;
  elements.submit.disabled = true;
  setResultState("running");
  pollJob();
} else if (initialRun) {
  loadRun(initialRun);
}
