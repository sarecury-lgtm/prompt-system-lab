import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller as CONTROLLER


class DummyEngine:
    pass


def policy():
    profile = CONTROLLER.OS.ModelProfile(
        model="fake",
        reasoning_effort="low",
        web_search=False,
        sandbox="read-only",
    )
    return {"router_fallback": profile}


def make_payload(
    route,
    *,
    execution_status="completed",
    contract_status="satisfied",
    missing=None,
    artifacts=None,
):
    execution = {
        "status": execution_status,
        "summary": "summary",
        "result_markdown": f"result from {route}",
        "capabilities_used": [],
        "needed_capability": None,
        "handoff": None,
        "artifacts": list(artifacts or []),
        "evidence": [],
        "limitations": [],
    }
    payload = {
        "goal_ledger": {
            "parent_goal": "사용자의 실제 결과",
            "fixed_constraints": ["조건을 보존한다."],
            "completion_condition": "쓸 수 있는 결과를 제공한다.",
        },
        "route": {
            "selected_route": route,
            "primary_route": None,
            "secondary_route": None,
            "route_reason": "test",
        },
        "execution": execution,
    }
    if contract_status is not None:
        payload["result_contract"] = {
            "validation": {
                "final_assessment": {
                    "overall_status": contract_status,
                    "missing_conditions": list(missing or []),
                }
            }
        }
    return payload


class SequenceRunner:
    def __init__(self, payloads):
        self.payloads = [copy.deepcopy(item) for item in payloads]
        self.calls = []

    def __call__(
        self,
        request,
        *,
        context_path,
        output_root,
        engine,
        model_policy,
        run_id,
    ):
        payload = copy.deepcopy(self.payloads[len(self.calls)])
        run_dir = output_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "result.md").write_text(
            payload["execution"]["result_markdown"],
            encoding="utf-8",
        )
        self.calls.append(
            {
                "request": request,
                "context_path": context_path,
                "run_id": run_id,
            }
        )
        return run_dir, payload


class SelectorSpy:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return copy.deepcopy(self.result)


class ControllerTests(unittest.TestCase):
    def test_completed_direct_stops_after_one_attempt(self):
        runner = SequenceRunner([make_payload("DIRECT")])
        selector = SelectorSpy(
            {
                "decision": "change_method",
                "target_route": "RESEARCH",
                "changed_dimension": "route",
                "reason": "unused",
                "expected_gain": "unused",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            controller_dir, _payload, state = CONTROLLER.run_controller_request(
                "주어진 댓글을 분석해 줘",
                output_root=Path(temp_dir),
                engine=DummyEngine(),
                model_policy=policy(),
                run_id="direct-complete",
                attempt_runner=runner,
                replan_selector=selector,
            )
            self.assertTrue((controller_dir / "controller_state.json").is_file())
            self.assertEqual("result from DIRECT", (controller_dir / "result.md").read_text())

        self.assertEqual(0, selector.calls)
        self.assertEqual(1, len(state["attempts"]))
        self.assertEqual("completed", state["outcome"])
        self.assertEqual("finish", state["decisions"][0]["action"])

    def test_partial_research_changes_route_once_and_finishes(self):
        runner = SequenceRunner(
            [
                make_payload(
                    "RESEARCH",
                    execution_status="partial",
                    contract_status="missing",
                    missing=["현재 근거 부족"],
                ),
                make_payload("DIRECT"),
            ]
        )
        selector = SelectorSpy(
            {
                "decision": "change_method",
                "target_route": "DIRECT",
                "changed_dimension": "route",
                "reason": "외부 사실이 아니라 제공 문맥 분석이 핵심이다.",
                "expected_gain": "불필요한 검색 없이 최종 분석을 완성한다.",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            controller_dir, _payload, state = CONTROLLER.run_controller_request(
                "이 논쟁의 핵심을 분석해 줘",
                output_root=Path(temp_dir),
                engine=DummyEngine(),
                model_policy=policy(),
                run_id="research-to-direct",
                attempt_runner=runner,
                replan_selector=selector,
            )
            retry_context = (controller_dir / "attempt-2-context.md").read_text(
                encoding="utf-8"
            )

        self.assertIn("select exactly DIRECT", retry_context)
        self.assertEqual(1, selector.calls)
        self.assertEqual(2, len(state["attempts"]))
        self.assertEqual(1, state["budget"]["used_method_changes"])
        self.assertEqual(2, state["chosen_attempt"])
        self.assertEqual("completed", state["outcome"])
        self.assertEqual("change_method", state["decisions"][0]["action"])

    def test_mutating_code_attempt_is_not_automatically_replanned(self):
        runner = SequenceRunner(
            [
                make_payload(
                    "CODE",
                    execution_status="partial",
                    contract_status="missing",
                    missing=["테스트 실패"],
                    artifacts=[
                        {
                            "path": "web/app.js",
                            "action": "modified",
                            "verification": "diff",
                        }
                    ],
                )
            ]
        )
        selector = SelectorSpy(
            {
                "decision": "change_method",
                "target_route": "PROJECT",
                "changed_dimension": "route",
                "reason": "unused",
                "expected_gain": "unused",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _controller_dir, _payload, state = CONTROLLER.run_controller_request(
                "기존 파일 버그를 고쳐 줘",
                output_root=Path(temp_dir),
                engine=DummyEngine(),
                model_policy=policy(),
                run_id="code-partial",
                attempt_runner=runner,
                replan_selector=selector,
            )

        self.assertEqual(0, selector.calls)
        self.assertEqual("partial", state["outcome"])
        self.assertEqual("stop_incomplete", state["decisions"][0]["action"])

    def test_replan_rejects_same_route(self):
        with self.assertRaisesRegex(CONTROLLER.ControllerError, "현재 route"):
            CONTROLLER.validate_replan_output(
                {
                    "replan": {
                        "decision": "change_method",
                        "target_route": "RESEARCH",
                        "changed_dimension": "route",
                        "reason": "다시 검색",
                        "expected_gain": "더 많은 자료",
                    }
                },
                "RESEARCH",
            )

    def test_controller_interface_summarizes_multiple_domains(self):
        routes = ["DIRECT", "RESEARCH", "REUSE", "PROMPT"]
        with tempfile.TemporaryDirectory() as temp_dir:
            summaries = [
                CONTROLLER.summarize_attempt(
                    index,
                    Path(temp_dir) / str(index),
                    make_payload(route),
                )
                for index, route in enumerate(routes, start=1)
            ]
        self.assertEqual(routes, [item["route"] for item in summaries])
        self.assertTrue(all(item["outcome"] == "completed" for item in summaries))

    def test_second_attempt_route_mismatch_cannot_replace_first(self):
        runner = SequenceRunner(
            [
                make_payload(
                    "DIRECT",
                    execution_status="partial",
                    contract_status="missing",
                    missing=["최신 사실 필요"],
                ),
                make_payload(
                    "REUSE",
                    execution_status="partial",
                    contract_status="missing",
                    missing=["실제 자산 없음"],
                ),
            ]
        )
        selector = SelectorSpy(
            {
                "decision": "change_method",
                "target_route": "RESEARCH",
                "changed_dimension": "route",
                "reason": "최신 사실을 확인한다.",
                "expected_gain": "현재 근거를 확보한다.",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _controller_dir, _payload, state = CONTROLLER.run_controller_request(
                "현재 정책을 확인해 줘",
                output_root=Path(temp_dir),
                engine=DummyEngine(),
                model_policy=policy(),
                run_id="route-mismatch",
                attempt_runner=runner,
                replan_selector=selector,
            )

        self.assertFalse(state["attempts"][1]["route_matches_controller"])
        self.assertEqual(1, state["chosen_attempt"])
        self.assertEqual("partial", state["outcome"])

    def test_blocked_before_routing_is_preserved(self):
        payload = make_payload(
            None,
            execution_status="blocked_by_capability",
            contract_status=None,
        )
        summary = CONTROLLER.summarize_attempt(1, Path("blocked"), payload)
        self.assertEqual("blocked", summary["outcome"])
        self.assertIsNone(summary["route"])
        self.assertFalse(CONTROLLER.can_change_method(summary, 0))


if __name__ == "__main__":
    unittest.main()
