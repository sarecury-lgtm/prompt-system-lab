import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_manual_revision.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_manual_revision_test",
    MODULE_PATH,
)
REVISION = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = REVISION
SPEC.loader.exec_module(REVISION)


def route_result(route="DIRECT"):
    reason = f"{route}가 가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "사용자의 실제 결과 확보",
            "current_goal_hypothesis": "요청을 그대로 해결",
            "fixed_constraints": ["요청 범위를 바꾸지 않음"],
            "current_position": "첫 실행",
            "selected_route": route,
            "secondary_route": None,
            "route_reason": reason,
            "current_step": "가장 가까운 결과 생성",
            "why_this_step_matters": "계획이 아니라 실제 결과가 필요함",
            "completion_condition": "사용 가능한 결과가 생성됨",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": route,
            "primary_route": None,
            "secondary_route": None,
            "route_reason": reason,
        },
    }


def execution_result(result, *, web=False):
    return {
        "execution": {
            "status": "completed",
            "summary": "결과 생성",
            "result_markdown": result,
            "capabilities_used": ["ai_reasoning", "web_search"] if web else ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": (
                [
                    {
                        "source": "https://example.com/product",
                        "finding": "현재 판매 상품을 확인했다.",
                        "kind": "web",
                    }
                ]
                if web
                else []
            ),
            "limitations": [],
        }
    }


class RoutePreservingRevisionTests(unittest.TestCase):
    def complete_parent(self, bridge, runs, route="DIRECT"):
        bridge.start(
            "현재 판매 상품을 추천해줘" if route == "RESEARCH" else "답변을 만들어줘",
            research_mode="standard" if route == "RESEARCH" else "none",
        )
        bridge.submit(
            "parent",
            json.dumps(route_result(route), ensure_ascii=False),
        )
        bridge.submit(
            "parent",
            json.dumps(
                execution_result("직전 결과", web=route == "RESEARCH"),
                ensure_ascii=False,
            ),
        )
        self.assertTrue((runs / "parent" / "result.md").is_file())

    def test_same_route_revision_skips_router_and_includes_prior_result(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = REVISION.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                REVISION.problem_os,
                "make_run_id",
                side_effect=["parent", "revision"],
            ):
                self.complete_parent(bridge, runs)
                session = bridge.revise(
                    "parent",
                    "문장 하나를 교체하고 규칙을 추가해라.",
                    "none",
                    "preserve_route",
                )
            self.assertEqual(session["state"], "awaiting_primary")
            self.assertEqual(session["route"], "DIRECT")
            self.assertNotIn("반환 계약: router", session["prompt"])
            self.assertIn("직전 결과", session["prompt"])
            self.assertIn("문장 하나를 교체", session["prompt"])
            record = json.loads(
                (runs / "revision" / "revision.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["revision_mode"], "preserve_route")

    def test_link_feedback_rejects_research_result_without_direct_url(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = REVISION.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                REVISION.problem_os,
                "make_run_id",
                side_effect=["parent", "revision"],
            ):
                self.complete_parent(bridge, runs, "RESEARCH")
                session = bridge.revise(
                    "parent",
                    "복숭아 실제 구매 링크가 결과에 하나도 없다.",
                    "standard",
                    "preserve_route",
                )
            self.assertEqual(session["state"], "awaiting_primary")
            self.assertIn("직접 상품 URL", session["prompt"])
            with self.assertRaises(REVISION.manual.ManualBridgeError):
                bridge.submit(
                    "revision",
                    json.dumps(
                        execution_result("후보 A를 추천합니다.", web=True),
                        ensure_ascii=False,
                    ),
                )
            self.assertIn(
                "직접 URL",
                bridge.get("revision")["error"],
            )

    def test_link_feedback_accepts_url_in_result_body(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = REVISION.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                REVISION.problem_os,
                "make_run_id",
                side_effect=["parent", "revision"],
            ):
                self.complete_parent(bridge, runs, "RESEARCH")
                bridge.revise(
                    "parent",
                    "각 복숭아 후보의 상품 페이지 링크를 본문에 넣어라.",
                    "standard",
                    "preserve_route",
                )
            finished = bridge.submit(
                "revision",
                json.dumps(
                    execution_result(
                        "후보 A\n구매 링크: https://example.com/product",
                        web=True,
                    ),
                    ensure_ascii=False,
                ),
            )
            self.assertEqual(finished["state"], "completed")
            route_record = json.loads(
                (runs / "revision" / "route.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                route_record["manual_bridge"]["revision_mode"],
                "preserve_route",
            )


if __name__ == "__main__":
    unittest.main()
