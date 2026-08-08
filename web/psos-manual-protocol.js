(() => {
  const START_MARKER = "<!-- PSOS_RESULT_ENVELOPE_START -->";
  const END_MARKER = "<!-- PSOS_RESULT_ENVELOPE_END -->";
  const ROUTES = new Set(["DIRECT", "RESEARCH", "DECISION", "CANDIDATE", "PROMPT", "WRITE"]);

  const ROUTE_PROCEDURES = {
    DIRECT: [
      "현재 대화와 제공 자료만으로 요청을 직접 해결한다.",
      "가장 가능성 높은 의도를 잡고 불필요한 중간 절차 없이 결과를 완성한다.",
      "결론을 바꾸는 정보가 부족할 때만 질문한다.",
    ],
    RESEARCH: [
      "최신 정보가 판단을 바꾸는 항목을 먼저 식별한다.",
      "웹 검색을 실제로 수행하고 변동 가능한 사실에 출처와 확인 시점을 연결한다.",
      "자료를 나열하지 말고 확인된 사실을 사용자의 질문에 대한 결론으로 연결한다.",
      "자료 충돌과 불확실성을 숨기지 않고 어떤 근거를 더 신뢰했는지 밝힌다.",
    ],
    DECISION: [
      "특정된 한 대상과 사용자가 고민하는 행동을 정확히 식별한다.",
      "최신 정보, 제공된 자료, 반대 근거와 실패 위험을 함께 확인한다.",
      "후보 목록이나 중간 작업대에서 멈추지 않고 요청에 맞는 행동 하나를 선택한다.",
      "판단을 바꾸는 조건과 실행 시 주의할 무효화 조건을 제시한다.",
    ],
    CANDIDATE: [
      "정보원 페이지가 아니라 사용자가 실제로 선택하거나 행동할 수 있는 대상을 후보로 만든다.",
      "접근 불가, 조건 불일치, 검증 부족과 치명적 위험이 있는 후보를 내부에서 제거한다.",
      "남은 후보를 같은 기준으로 비교하고 필요한 경우 추가 조사한다.",
      "소수 후보와 최종 1순위를 제시하거나, 통과한 후보가 없다고 분명히 결론낸다.",
    ],
    PROMPT: [
      "다른 AI가 실제 작업을 바로 수행할 수 있도록 목표, 고정 조건, 절차와 완료 조건을 통합한다.",
      "프롬프트 작성 과정이나 PSOS 내부 구조는 결과에 노출하지 않는다.",
      "같은 의미를 반복하지 않고 복사해 바로 사용할 최종 프롬프트 하나를 완성한다.",
    ],
    WRITE: [
      "사용자가 제공한 파일과 허용 범위를 기준으로 변경 목표를 식별한다.",
      "기존 기능을 보존하면서 필요한 변경만 설계한다.",
      "실제 적용 가능한 전체 파일 또는 통합 diff와 검증 방법을 제시한다.",
      "로컬 파일을 직접 수정했다고 주장하지 않고 적용 전 위험과 필요한 확인을 밝힌다.",
    ],
  };

  const ROUTE_GATES = {
    DIRECT: [
      "질문에 직접 답했는가",
      "사용자의 표현과 고정 조건을 다른 문제로 바꾸지 않았는가",
      "설명만 있고 실제 결과가 없는 상태로 끝나지 않았는가",
    ],
    RESEARCH: [
      "변동 가능한 핵심 주장에 출처와 확인 시점이 있는가",
      "출처가 실제 결론을 뒷받침하는가",
      "조사 목록이 아니라 사용자가 판단할 결론이 있는가",
    ],
    DECISION: [
      "매수·대기·회피 또는 구매·보류처럼 행동 결론이 하나로 정해졌는가",
      "가장 큰 반대 근거와 하방 위험을 반영했는가",
      "판단이 바뀌는 조건이 구체적인가",
    ],
    CANDIDATE: [
      "후보가 정보원이 아니라 실제 선택 대상인가",
      "모든 후보가 최소 검증 기준과 사용자 조건을 통과했는가",
      "동일 기준 비교와 최종 순위 또는 무승자 결론이 있는가",
    ],
    PROMPT: [
      "다른 AI가 추가 해석 없이 바로 실행할 수 있는가",
      "목표·고정 조건·절차·완료 조건이 보존됐는가",
      "내부 생성 과정이나 중복 지시가 결과를 흐리지 않는가",
    ],
    WRITE: [
      "변경 대상과 범위가 구체적인가",
      "기존 기능 보존과 검증 절차가 포함됐는가",
      "실제 적용되지 않은 변경을 적용 완료로 주장하지 않았는가",
    ],
  };

  function nowIso() {
    return new Date().toISOString();
  }

  function createJobId() {
    const stamp = nowIso().replace(/[-:.TZ]/g, "");
    const random = Math.random().toString(36).slice(2, 8);
    return `manual-${stamp}-${random}`;
  }

  function uniqueStrings(values) {
    const output = [];
    (Array.isArray(values) ? values : []).forEach((value) => {
      const text = String(value || "").trim();
      if (text && !output.includes(text)) output.push(text);
    });
    return output;
  }

  function inferRoute(request, externalHint = "") {
    const normalizedHint = String(externalHint || "").trim().toUpperCase();
    if (ROUTES.has(normalizedHint)) return normalizedHint;

    const text = String(request || "").trim();
    const writeTarget = /(코드|파일|폴더|웹페이지|웹사이트|앱|프로젝트|저장소|레포|repository|html|css|javascript|typescript|python|스크립트)/i.test(text);
    const writeAction = /(만들|구현|수정|고쳐|추가|삭제|리팩터|저장|적용|배포|완성)/i.test(text);
    if (writeTarget && writeAction) return "WRITE";

    const promptWord = /(프롬프트|prompt)/i.test(text);
    const promptAction = /(만들|작성|설계|생성|짜|다듬|개선|최적화)/i.test(text);
    if (promptWord && promptAction) return "PROMPT";

    const decisionAction = /(살까|매수|진입|매도|팔까|대기|회피|보유|손절|구매할까|사도 될까|해야 할까|어떻게 해야)/i.test(text);
    const broadSearch = /(추천|후보|여러|몇 개|찾아|골라|비교|가장 좋은|1위)/i.test(text);
    if (decisionAction && !broadSearch) return "DECISION";

    if (broadSearch) return "CANDIDATE";

    const currentWord = /(최신|오늘|현재|지금|가격|뉴스|법|규정|일정|패치|버전|검색|조사|찾아|확인|검증|판매 중|재고|실적)/i.test(text);
    if (currentWord) return "RESEARCH";
    return "DIRECT";
  }

  function completionRule(route) {
    if (route === "DECISION") {
      return "사용자가 지금 취할 행동 하나, 그 근거와 가장 큰 위험, 판단이 바뀌는 조건이 제시되면 완료다.";
    }
    if (route === "CANDIDATE") {
      return "검증 기준을 통과한 실제 후보만 비교되고 최종 1순위 또는 통과 후보 없음이 명확하면 완료다.";
    }
    if (route === "RESEARCH") {
      return "최신 근거와 확인 시점이 결론에 연결되고 사용자가 바로 판단할 답이 제시되면 완료다.";
    }
    if (route === "PROMPT") {
      return "다른 AI가 바로 실행할 수 있는 최종 프롬프트 하나가 완성되면 완료다.";
    }
    if (route === "WRITE") {
      return "적용 가능한 변경안과 검증 방법이 제시되고 실제 적용 여부가 정직하게 구분되면 완료다.";
    }
    return "사용자의 질문에 직접 답하고 바로 사용할 결과가 제시되면 완료다.";
  }

  function buildJobPacket({
    request,
    routeHint = "",
    context = "",
    previousAnswer = "",
    previousEnvelope = null,
    correction = "",
    attachments = [],
    jobId = "",
  }) {
    const cleanRequest = String(request || "").trim();
    if (!cleanRequest) throw new Error("사용자 요청이 비어 있습니다.");
    const route = inferRoute(cleanRequest, routeHint);
    const continuation = Boolean(previousAnswer || previousEnvelope || correction);
    const preserve = uniqueStrings([
      "사용자가 직접 명시한 목표와 조건",
      "대상, 주체, 시간 범위와 행동 주체",
      "이전 결과에서 이미 검증된 사실",
      continuation ? "이전 결과의 제외 후보와 보존 조건" : "",
    ]);

    return {
      version: 1,
      job_id: String(jobId || createJobId()),
      created_at: nowIso(),
      execution_provider: "chatgpt-manual",
      route_hint: route,
      user_request: cleanRequest,
      goal_ledger_task: {
        derive: [
          "parent_goal",
          "current_goal",
          "fixed_constraints",
          "current_position",
          "completion_condition",
          "important_uncertainties",
        ],
        preserve,
        ask_only_when:
          "누락된 정보가 결론을 크게 바꾸고 합리적인 기본값으로 진행할 수 없을 때만 질문한다.",
      },
      execution_contract: {
        procedure: [
          "사용자 요청에서 Goal Ledger를 내부적으로 구성한다.",
          "요청에 필요한 해결 경로와 도구를 선택한다.",
          ...(ROUTE_PROCEDURES[route] || ROUTE_PROCEDURES.DIRECT),
          "완료 조건과 품질 게이트를 기준으로 결과를 자체 점검한다.",
          "사용자 답변을 먼저 제시하고 Result Envelope를 마지막에 반환한다.",
        ],
        quality_gates: [
          "사용자 요청을 다른 문제로 바꾸지 않는다.",
          "검증하지 않은 사실을 확정적으로 만들지 않는다.",
          "중간 계획이나 후보 작업대가 아니라 실제 결과까지 완성한다.",
          ...(ROUTE_GATES[route] || ROUTE_GATES.DIRECT),
        ],
        completion_rule: completionRule(route),
        failure_rule:
          "완료 조건을 충족하지 못하면 억지 결론을 만들지 말고 가능한 결과와 부족한 항목을 분리해 partial 또는 blocked로 기록한다.",
      },
      inputs: {
        context: String(context || "").trim(),
        previous_answer: String(previousAnswer || "").trim(),
        previous_envelope: previousEnvelope && typeof previousEnvelope === "object"
          ? previousEnvelope
          : null,
        correction: String(correction || "").trim(),
        attachments: uniqueStrings(attachments),
      },
      output_contract: {
        answer_first: true,
        envelope_required: true,
        start_marker: START_MARKER,
        end_marker: END_MARKER,
      },
    };
  }

  function envelopeExample(jobId, route) {
    return {
      version: 1,
      job_id: jobId,
      status: "completed",
      route,
      goal: {
        parent: "",
        current: "",
        constraints: [],
        completion_condition: "",
      },
      decision: {
        conclusion: "",
        action: "",
        confidence: "medium",
        change_conditions: [],
      },
      completion: {
        met: true,
        missing: [],
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

  function buildExecutionPrompt(packet) {
    const example = envelopeExample(packet.job_id, packet.route_hint);
    return `당신은 아래 PSOS Job Packet을 실제로 실행하는 문제 해결 엔진이다. 패킷을 설명하거나 평가하는 데서 멈추지 말고 사용자 요청을 끝까지 해결하라.

[실행 규칙]
1. 먼저 패킷의 goal_ledger_task에 따라 목표, 고정 조건, 현재 위치, 완료 조건과 불확실성을 내부적으로 정리한다.
2. 그 내부 정리를 사용자에게 단계별 사고 과정으로 노출하지 않는다.
3. execution_contract의 절차와 품질 게이트를 적용해 실제 조사·분석·판단·작성 작업을 수행한다.
4. 최신 정보가 필요하면 웹 검색을 실제로 사용하고 변동 가능한 핵심 사실에 출처와 확인 시점을 연결한다.
5. 이전 결과와 교정이 있으면 맞는 사실과 보존 조건은 유지하고 필요한 부분만 갱신한다.
6. 답변 첫 부분에는 사용자가 읽을 최종 결과만 쓴다. 결론을 앞에 두고 근거, 위험, 불확실성과 다음 행동을 필요한 만큼 붙인다.
7. 마지막에는 아래 두 마커 사이에 JSON Result Envelope 하나를 넣는다. JSON 밖의 주석, 말줄임표와 예시 문구를 넣지 않는다.
8. 관련 없는 배열은 빈 배열로 둔다. 확인하지 못한 값은 만들어내지 말고 빈 문자열 또는 unresolved에 기록한다.
9. status는 완료 조건 충족 시 completed, 일부만 가능하면 partial, 핵심 능력이나 자료가 없어 수행 불가능하면 blocked다.
10. private chain-of-thought를 출력하지 않는다.

[Result Envelope 형식]
${START_MARKER}
\`\`\`json
${JSON.stringify(example, null, 2)}
\`\`\`
${END_MARKER}

[PSOS Job Packet]
\`\`\`json
${JSON.stringify(packet, null, 2)}
\`\`\`
`;
  }

  function stripFence(value) {
    return String(value || "")
      .trim()
      .replace(/^```(?:json)?\s*/i, "")
      .replace(/\s*```$/i, "")
      .trim();
  }

  function validateEnvelope(value, jobId = "") {
    const warnings = [];
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { envelope: null, warnings: ["Result Envelope가 JSON 객체가 아닙니다."] };
    }
    const envelope = { ...value };
    if (envelope.version !== 1) warnings.push("지원하는 Result Envelope 버전이 아닙니다.");
    if (jobId && envelope.job_id !== jobId) warnings.push("Job Packet과 Result Envelope의 job_id가 다릅니다.");
    if (!["completed", "partial", "blocked"].includes(envelope.status)) {
      warnings.push("status가 올바르지 않아 partial로 처리합니다.");
      envelope.status = "partial";
    }
    if (!ROUTES.has(String(envelope.route || "").toUpperCase())) {
      warnings.push("route가 올바르지 않습니다.");
    }
    if (!envelope.completion || typeof envelope.completion.met !== "boolean") {
      warnings.push("완료 검증 정보가 없습니다.");
    }
    envelope.evidence = Array.isArray(envelope.evidence) ? envelope.evidence : [];
    envelope.candidates = Array.isArray(envelope.candidates) ? envelope.candidates : [];
    envelope.artifacts = Array.isArray(envelope.artifacts) ? envelope.artifacts : [];
    envelope.continuation = envelope.continuation && typeof envelope.continuation === "object"
      ? envelope.continuation
      : { preserve: [], excluded_candidate_ids: [], unresolved: [] };
    return { envelope, warnings };
  }

  function parseResultEnvelope(text, expectedJobId = "") {
    const raw = String(text || "").trim();
    const start = raw.lastIndexOf(START_MARKER);
    const end = raw.lastIndexOf(END_MARKER);
    if (start >= 0 && end > start) {
      const answer = raw.slice(0, start).trim();
      const jsonText = stripFence(raw.slice(start + START_MARKER.length, end));
      try {
        const parsed = JSON.parse(jsonText);
        const validated = validateEnvelope(parsed, expectedJobId);
        return {
          answer: answer || raw,
          envelope: validated.envelope,
          warnings: validated.warnings,
          imported: Boolean(validated.envelope),
        };
      } catch (error) {
        return {
          answer: answer || raw,
          envelope: null,
          warnings: [`Result Envelope JSON을 읽지 못했습니다: ${error.message}`],
          imported: false,
        };
      }
    }

    const fenced = Array.from(raw.matchAll(/```json\s*([\s\S]*?)```/gi)).reverse();
    for (const match of fenced) {
      try {
        const parsed = JSON.parse(match[1]);
        if (parsed && parsed.version === 1 && parsed.job_id) {
          const validated = validateEnvelope(parsed, expectedJobId);
          return {
            answer: raw.replace(match[0], "").trim() || raw,
            envelope: validated.envelope,
            warnings: ["마커 없이 JSON 블록을 찾아 가져왔습니다.", ...validated.warnings],
            imported: Boolean(validated.envelope),
          };
        }
      } catch (_error) {
        // Continue to the next JSON block.
      }
    }

    return {
      answer: raw,
      envelope: null,
      warnings: ["Result Envelope가 없어 일반 답변으로만 저장합니다."],
      imported: false,
    };
  }

  function buildContinuationPrompt({ packet, previousAnswer, previousEnvelope, correction }) {
    const nextPacket = buildJobPacket({
      request: packet.user_request,
      routeHint: packet.route_hint,
      context: packet.inputs?.context || "",
      previousAnswer,
      previousEnvelope,
      correction,
      attachments: packet.inputs?.attachments || [],
      jobId: packet.job_id,
    });
    return buildExecutionPrompt(nextPacket);
  }

  function toDisplayData({ packet, imported }) {
    const envelope = imported.envelope;
    const evidence = envelope?.evidence.map((item) => ({
      source: item.source || item.url || "ChatGPT 수동 실행",
      finding: [item.finding, item.checked_at ? `확인: ${item.checked_at}` : ""]
        .filter(Boolean)
        .join(" · "),
    })) || [];
    const artifacts = envelope?.artifacts.map((item) => ({
      path: item.path || "경로 없음",
      action: item.action || "none",
    })) || [];
    const limitations = [...imported.warnings];
    if (envelope?.completion?.missing?.length) {
      limitations.push(...envelope.completion.missing);
    }
    return {
      run_id: packet.job_id,
      route: `MANUAL CHATGPT · ${envelope?.route || packet.route_hint}`,
      execution_status: envelope?.status || "partial",
      result_markdown: imported.answer,
      evidence,
      artifacts,
      limitations,
      workspace_receipt: null,
      workspace_rollback: null,
    };
  }

  window.PSOSManualProtocol = Object.freeze({
    version: 1,
    START_MARKER,
    END_MARKER,
    inferRoute,
    buildJobPacket,
    buildExecutionPrompt,
    parseResultEnvelope,
    buildContinuationPrompt,
    toDisplayData,
  });
})();
