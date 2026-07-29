import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_os.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_os", MODULE_PATH)
OS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = OS
SPEC.loader.exec_module(OS)


def engine_result(
    route="DIRECT",
    *,
    primary=None,
    secondary=None,
    status="completed",
    artifacts=None,
    evidence=None,
):
    reason = f"{route}가 가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "사용자의 실제 결과 확보",
            "current_goal_hypothesis": "요청을 그대로 해결",
            "fixed_constraints": ["요청의 범위를 바꾸지 않음"],
            "current_position": "첫 실행",
            "selected_route": route,
            "secondary_route": secondary,
            "route_reason": reason,
            "current_step": "가장 가까운 결과 생성",
            "why_this_step_matters": "계획이 아니라 실제 결과가 필요함",
            "completion_condition": "사용 가능한 결과가 생성됨",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": route,
            "primary_route": primary,
            "secondary_route": secondary,
            "route_reason": reason,
        },
        "execution": {
            "status": status,
            "summary": "결과 생성",
            "result_markdown": "실제로 생성된 결과입니다.",
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": artifacts or [],
            "evidence": evidence or [],
            "limitations": [],
        },
    }


class FakeEngine:
    def __init__(self, payload, capabilities=None):
        self.payload = payload
        self.prompt = ""
        self._capabilities = capabilities or OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="fixture",
        )

    def capabilities(self):
        return self._capabilities

    def execute(self, prompt, run_dir):
        self.prompt = prompt
        return json.loads(json.dumps(self.payload))


class ProblemSolvingOSTests(unittest.TestCase):
    def test_direct_run_creates_required_artifacts_and_compact_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = OS.run_request(
                "캐시가 무엇인지 설명해 줘.",
                output_root=Path(temp_dir),
                engine=FakeEngine(engine_result()),
                run_id="direct",
            )
            self.assertEqual("completed", payload["execution"]["status"])
            for name in ("request.txt", "goal_ledger.json", "route.json", "result.md"):
                self.assertTrue((run_dir / name).is_file(), name)
            result = (run_dir / "result.md").read_text(encoding="utf-8")
            self.assertIn("현재 목표:", result)
            self.assertIn("선택한 해결 방식: DIRECT", result)
            self.assertNotIn("parent_goal", result)

    def test_context_file_is_supplied_to_ai_engine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = root / "context.md"
            context.write_text("고정 독자: 신규 입사자", encoding="utf-8")
            engine = FakeEngine(engine_result())
            OS.run_request(
                "안내문을 작성해 줘.",
                context_path=context,
                output_root=root / "runs",
                engine=engine,
                run_id="context",
            )
            self.assertIn("고정 독자: 신규 입사자", engine.prompt)
            self.assertIn(str(context.resolve()), engine.prompt)

    def test_research_without_search_is_honestly_blocked(self):
        capabilities = OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=False,
            workspace_read=True,
            workspace_write=False,
            detail="search disabled",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "오늘 노트북 가격을 조사해 줘.",
                output_root=Path(temp_dir),
                engine=FakeEngine(engine_result("RESEARCH"), capabilities),
                run_id="research-blocked",
            )
        self.assertEqual("blocked_by_capability", payload["execution"]["status"])
        self.assertEqual("live web search", payload["execution"]["needed_capability"])
        self.assertFalse(payload["execution"]["evidence"])

    def test_hybrid_requires_exactly_one_primary_and_secondary_route(self):
        payload = engine_result(
            "HYBRID", primary="RESEARCH", secondary="PROMPT"
        )
        validated = OS.validate_engine_output(
            payload,
            OS.EngineCapabilities(True, True, True, False, "fixture"),
        )
        self.assertEqual("RESEARCH", validated["route"]["primary_route"])
        payload["route"]["secondary_route"] = "RESEARCH"
        payload["goal_ledger"]["secondary_route"] = "RESEARCH"
        with self.assertRaises(OS.ProblemSolvingError):
            OS.validate_engine_output(
                payload,
                OS.EngineCapabilities(True, True, True, False, "fixture"),
            )

    def test_single_route_duplicate_primary_is_normalized(self):
        payload = engine_result("DIRECT")
        payload["route"]["primary_route"] = "DIRECT"
        payload["route"]["route_reason"] = "더 구체적인 공개 이유"
        validated = OS.validate_engine_output(
            payload,
            OS.EngineCapabilities(True, True, True, False, "fixture"),
        )
        self.assertIsNone(validated["route"]["primary_route"])
        self.assertEqual(
            "더 구체적인 공개 이유",
            validated["goal_ledger"]["route_reason"],
        )

    def test_prompt_route_reuses_existing_prompt_compiler(self):
        payload = engine_result("PROMPT")
        payload["execution"]["limitations"] = ["컴파일 전 임시 한계"]
        compiled = {
            "final_prompt": "기존 Compiler 결과",
            "selected_mode": "baseline",
            "selection_reason": "baseline-first",
            "used_patterns": [],
            "used_active_sources": [],
            "fallback": False,
            "fallback_reason": "",
        }
        runtime = mock.Mock()
        runtime.create_prompt.return_value = compiled
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(OS, "load_prompt_runtime", return_value=runtime):
                run_dir, result = OS.run_request(
                    "다른 AI에서 반복할 지침을 만들어 줘.",
                    output_root=Path(temp_dir),
                    engine=FakeEngine(payload),
                    run_id="prompt",
                )
            self.assertIn(
                "기존 Compiler 결과",
                (run_dir / "result.md").read_text(encoding="utf-8"),
            )
            self.assertIn("prompt_compiler", result)
            self.assertEqual([], result["execution"]["limitations"])
            runtime.create_prompt.assert_called_once()

    def test_hybrid_prompt_preserves_primary_result(self):
        payload = engine_result(
            "HYBRID",
            primary="RESEARCH",
            secondary="PROMPT",
        )
        compiled = {
            "final_prompt": "기존 Compiler 결과",
            "selected_mode": "baseline",
            "selection_reason": "baseline-first",
            "used_patterns": [],
            "used_active_sources": [],
            "fallback": False,
            "fallback_reason": "",
        }
        runtime = mock.Mock()
        runtime.create_prompt.return_value = compiled
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(OS, "load_prompt_runtime", return_value=runtime):
                run_dir, result = OS.run_request(
                    "조사 후 반복 지침을 만들어 줘.",
                    output_root=Path(temp_dir),
                    engine=FakeEngine(payload),
                    run_id="hybrid-prompt",
                )
            self.assertIn("실제로 생성된 결과입니다.", result["execution"]["result_markdown"])
            self.assertIn("기존 Compiler 결과", result["execution"]["result_markdown"])
            compiler_context = run_dir / "prompt-compiler-context.md"
            self.assertTrue(compiler_context.is_file())
            self.assertIn(
                "실제로 생성된 결과입니다.",
                compiler_context.read_text(encoding="utf-8"),
            )
            compiler_paths = runtime.create_prompt.call_args.args[1]
            self.assertIn(compiler_context, compiler_paths)

    def test_write_claim_is_rejected_when_workspace_is_read_only(self):
        payload = engine_result(
            "CODE",
            artifacts=[
                {
                    "path": "example.py",
                    "action": "modified",
                    "verification": "claimed",
                }
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _, result = OS.run_request(
                "파일을 자동 처리해 줘.",
                output_root=Path(temp_dir),
                engine=FakeEngine(payload),
                run_id="write-claim",
            )
        self.assertEqual("blocked_by_capability", result["execution"]["status"])
        self.assertIn("쓰기 capability", result["execution"]["limitations"][0])

    def test_missing_ai_engine_saves_blocked_run_without_guessing_route(self):
        capabilities = OS.EngineCapabilities(False, False, False, False, "missing")
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, result = OS.run_request(
                "막연한 요청",
                output_root=Path(temp_dir),
                engine=FakeEngine(engine_result(), capabilities),
                run_id="missing-engine",
            )
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertIsNone(route["selected_route"])
            self.assertEqual("blocked_by_capability", result["execution"]["status"])

    def test_goal_ledger_rejects_more_than_three_uncertainties(self):
        payload = engine_result()
        payload["goal_ledger"]["important_uncertainties"] = ["1", "2", "3", "4"]
        with self.assertRaises(OS.ProblemSolvingError):
            OS.validate_engine_output(
                payload,
                OS.EngineCapabilities(True, True, True, False, "fixture"),
            )


if __name__ == "__main__":
    unittest.main()
