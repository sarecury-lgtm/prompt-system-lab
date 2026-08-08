(() => {
  const legacy = window.PSOSManualProtocol;
  if (!legacy) return;

  function text(value) {
    return String(value || "").trim();
  }

  function unique(values) {
    return Array.from(new Set((Array.isArray(values) ? values : []).map(text).filter(Boolean)));
  }

  function receiptExample(packet, status = "completed", met = true, missing = []) {
    return {
      version: 1,
      job_id: packet.job_id,
      status,
      route: packet.route_hint,
      completion: {
        met,
        missing,
      },
      evidence: [],
      candidates: [],
      artifacts: [],
      continuation: {
        preserve: [],
        excluded_candidate_ids: [],
        unresolved: [],
      },
    };
  }

  function contextBlock(packet) {
    const inputs = packet.inputs || {};
    const blocks = [];
    if (text(inputs.context)) {
      blocks.push(`[현재 대화에서 제공된 추가 문맥]\n${text(inputs.context)}`);
    }
    if (text(inputs.previous_answer)) {
      blocks.push(`[이전 결과]\n${text(inputs.previous_answer)}`);
    }
    if (text(inputs.correction)) {
      blocks.push(`[사용자의 최신 교정]\n${text(inputs.correction)}`);
    }
    const attachments = unique(inputs.attachments);
    if (attachments.length) {
      blocks.push(`[현재 대화에 함께 첨부할 파일/이미지]\n${attachments.map((item) => `- ${item}`).join("\n")}`);
    }
    return blocks.length ? `\n\n${blocks.join("\n\n")}` : "";
  }

  function buildThinExecutionPrompt(packet) {
    const receipt = receiptExample(packet);
    return `아래 사용자 요청을 자연스럽게 해결하세요. 정해진 워크플로를 수행하거나 내부 구조를 설명하는 것이 목적이 아니라, 사용자의 실제 목적에 가장 좋은 결과를 내는 것이 목적입니다.

[최소 가드레일]
- 사용자의 실제 목적과 명시된 조건을 보존하고 더 익숙한 다른 문제로 바꾸지 마세요.
- 현재 대화에서 실제로 제공된 내용과 첨부 파일만 사용자별 근거로 사용하세요. 사용자가 말하지 않은 취향이나 경험을 지어내지 마세요.
- 결과를 크게 바꾸는 정보가 부족하면 한 번에 1~2개만 질문하세요. 답을 받은 뒤 다시 정보 충분성을 판단할 수 있으며, 질문을 한 번으로 끝낼 필요는 없습니다.
- 음식·여행·제품·진로 등 주관적 추천에서 핵심 선호가 없으면 최종 1순위를 먼저 정하지 마세요. 사용자의 추상적 선호를 특정 브랜드·품종·제품군의 선호로 바로 치환하지 말고 서로 다른 합리적 후보 방향을 열어 두세요.
- 추천이나 선택을 할 때는 가능하면 '사용자 목적/선호 → 후보의 관련 특성 → 근거 → 주요 대안보다 적합한 이유'가 드러나게 설명하세요. 근거가 부족하면 억지 순위를 만들지 마세요.
- 최신 정보가 필요하면 실제 검색을 사용하고, 확인된 사실·추론·미확인을 구분하세요. 판매자·브랜드·가격·별점 같은 proxy를 실제 개별 품질로 승격하지 마세요.
- 사용자가 놓친 변수, 반대 가능성, 결론을 바꿀 조건이 중요하면 찾아보세요. 단순히 새로운 말이 아니라 실제 판단을 바꾸는 내용만 반영하세요.
- 현재 답이 최종 목적의 중간 단계이고 같은 목적을 더 진행할 명확한 다음 행동이 있으면, 막연한 '더 도와드릴까요?' 대신 구체적인 다음 행동 1~2개를 제안하세요.
- 후속 교정이 오면 맞는 부분은 보존하고 바뀐 조건만 갱신하세요.
- 단순한 요청은 단순하게 답하세요. 위 규칙을 체크리스트처럼 사용자에게 노출하지 마세요.

[사용자 요청]
${text(packet.user_request)}${contextBlock(packet)}

답변이 완성된 뒤 작업실 상태 기록을 위해 마지막에 아래 두 마커 사이에 작은 JSON receipt 하나만 붙이세요. 내부 사고 과정은 넣지 마세요. 질문이 더 필요해 아직 결과가 완성되지 않았다면 status를 partial, completion.met을 false로 하고 missing에 필요한 사용자 답을 적으세요.

${legacy.START_MARKER}
\`\`\`json
${JSON.stringify(receipt, null, 2)}
\`\`\`
${legacy.END_MARKER}`;
  }

  function buildThinContinuationPrompt({ packet, correction }) {
    const cleanCorrection = text(correction);
    const receipt = receiptExample(packet);
    return `같은 작업을 이어서 수정하세요. 새 작업으로 초기화하지 말고 이전 답변에서 여전히 맞는 사실·근거·선택지는 보존하세요.

[사용자의 최신 교정]
${cleanCorrection || "사용자가 결과를 더 다듬어 달라고 요청했습니다."}

바뀐 조건과 직접 관련된 부분만 다시 판단하되, 이전 전제가 틀렸다면 보존하지 마세요. 필요한 경우 추가 질문·검색·비교를 자연스럽게 수행하세요. 추천을 바꾸면 왜 바뀌었는지 사용자 조건과 근거를 연결해 설명하세요. 현재 결과가 중간 단계라면 같은 목적을 더 진행할 구체적인 다음 행동을 제안할 수 있습니다.

완료 후 사용자용 결과를 먼저 쓰고 마지막에 아래 receipt를 갱신해 붙이세요.

${legacy.START_MARKER}
\`\`\`json
${JSON.stringify(receipt, null, 2)}
\`\`\`
${legacy.END_MARKER}`;
  }

  window.PSOSManualProtocolLegacy = legacy;
  window.PSOSManualProtocol = Object.freeze({
    ...legacy,
    version: "1-thin",
    buildExecutionPrompt: buildThinExecutionPrompt,
    buildContinuationPrompt: buildThinContinuationPrompt,
  });

  queueMicrotask(() => {
    const toggleTitle = document.querySelector(".manual-v5-toggle strong");
    const toggleCopy = document.querySelector(".manual-v5-toggle small");
    if (toggleTitle) toggleTitle.textContent = "ChatGPT 수동 실행 · 실험용";
    if (toggleCopy) toggleCopy.textContent = "매 턴 복사·붙여넣기가 필요한 진단 경로입니다. Codex 소진 시에는 위의 Blind handoff를 우선 사용하세요.";

    const panel = document.querySelector("#chatgpt-manual-panel");
    if (!panel) return;
    const kicker = panel.querySelector(".manual-v5-heading .workflow-kicker");
    const title = panel.querySelector(".manual-v5-heading h3");
    const description = panel.querySelector(".manual-v5-heading p");
    const copyButton = panel.querySelector("#manual-v5-copy");
    const detailsSummary = panel.querySelector("#manual-v5-packet-details summary");
    const firstStep = panel.querySelector('.manual-v5-progress li[data-step="1"] span');

    if (kicker) kicker.textContent = "진단용 대화 우선 실행";
    if (title) title.textContent = "모델의 자연스러운 문제 해결은 살리고 반복 실패만 얇게 막습니다.";
    if (description) description.textContent = "질문·검색·추론을 고정된 Controller 단계에 가두지 않고, 필요한 순간에만 최소 가드레일을 적용합니다.";
    if (copyButton) copyButton.textContent = "실행 요청 복사";
    if (detailsSummary) detailsSummary.textContent = "보낼 요청 확인";
    if (firstStep) firstStep.textContent = "요청 복사";
  });
})();
