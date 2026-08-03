const assert = require("node:assert/strict");

global.window = {};
require("../web/psos-manual-protocol.js");

const protocol = global.window.PSOSManualProtocol;
assert.ok(protocol, "manual protocol must be installed");

const packet = protocol.buildJobPacket({
  request: "토스트 주식을 오늘 매수하는 게 좋을까? 내일 실적 발표야.",
});
assert.equal(packet.version, 1);
assert.equal(packet.route_hint, "DECISION");
assert.ok(packet.goal_ledger_task.derive.includes("completion_condition"));
assert.ok(packet.execution_contract.quality_gates.length >= 4);

const prompt = protocol.buildExecutionPrompt(packet);
assert.ok(prompt.includes("PSOS Job Packet"));
assert.ok(prompt.includes(protocol.START_MARKER));
assert.ok(prompt.includes(packet.job_id));

const envelope = {
  version: 1,
  job_id: packet.job_id,
  status: "completed",
  route: "DECISION",
  goal: {
    parent: "실적 전 매수 여부 판단",
    current: "토스트 신규 매수 결정",
    constraints: ["내일 실적 발표"],
    completion_condition: "매수·대기·회피 중 하나를 결정한다.",
  },
  decision: {
    conclusion: "실적 전 신규 매수는 대기",
    action: "대기",
    confidence: "medium",
    change_conditions: ["실적 후 갭을 지지하고 돌파"],
  },
  completion: { met: true, missing: [] },
  evidence: [],
  candidates: [],
  artifacts: [],
  continuation: {
    preserve: ["실적 일정"],
    excluded_candidate_ids: [],
    unresolved: [],
  },
};

const response = [
  "## 결론",
  "실적 전 신규 매수는 대기하는 편이 낫습니다.",
  protocol.START_MARKER,
  "```json",
  JSON.stringify(envelope, null, 2),
  "```",
  protocol.END_MARKER,
].join("\n");

const imported = protocol.parseResultEnvelope(response, packet.job_id);
assert.equal(imported.imported, true);
assert.equal(imported.envelope.decision.action, "대기");
assert.ok(imported.answer.includes("실적 전 신규 매수"));
assert.deepEqual(imported.warnings, []);

const continuation = protocol.buildContinuationPrompt({
  packet,
  previousAnswer: imported.answer,
  previousEnvelope: imported.envelope,
  correction: "소액 진입 가능성도 비교해.",
});
assert.ok(continuation.includes("소액 진입 가능성도 비교해."));
assert.ok(continuation.includes("실적 전 신규 매수는 대기"));
assert.ok(continuation.includes(packet.job_id));

const fallback = protocol.parseResultEnvelope("일반 답변만 있습니다.", packet.job_id);
assert.equal(fallback.imported, false);
assert.equal(fallback.answer, "일반 답변만 있습니다.");
assert.ok(fallback.warnings.length === 1);

console.log("manual protocol smoke test passed");
