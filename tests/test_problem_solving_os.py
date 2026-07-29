import importlib.util
import json
import subprocess
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


def route_result(route="DIRECT", *, primary=None, secondary=None):
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
    }


def execution_result(
    *,
    status="completed",
    result="실제로 생성된 결과입니다.",
    artifacts=None,
    evidence=None,
    limitations=None,
):
    return {
        "execution": {
            "status": status,
            "summary": "결과 생성",
            "result_markdown": result,
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": artifacts or [],
            "evidence": evidence or [],
            "limitations": limitations or [],
        }
    }


class FakeEngine:
    def __init__(self, responses, capabilities=None):
        self.responses = list(responses)
        self.calls = []
        self._capabilities = capabilities or OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="fixture",
        )

    def capabilities(self):
        return self._capabilities

    def execute(self, prompt, run_dir, invocation):
        self.calls.append({"prompt": prompt, "invocation": invocation})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.loads(json.dumps(response))

    def trace(self):
        return [
            {
                "name": call["invocation"].name,
                "phase": call["invocation"].phase,
                "route": call["invocation"].route,
                "model": call["invocation"].profile.model,
                "reasoning_effort": call["invocation"].profile.reasoning_effort,
            }
            for call in self.calls
        ]


class ProblemSolvingOSTests(unittest.TestCase):
    def setUp(self):
        self.policy = OS.load_model_policy()

    def test_model_policy_assigns_explicit_models_and_tools(self):
        self.assertEqual("gpt-5.6-luna", self.policy["router"].model)
        self.assertEqual("low", self.policy["router"].reasoning_effort)
        self.assertEqual(
            "gpt-5.6-terra",
            self.policy["routes"]["DIRECT"]["primary"].model,
        )
        self.assertEqual(
            "gpt-5.6-sol",
            self.policy["routes"]["CODE"]["primary"].model,
        )
        self.assertTrue(self.policy["routes"]["RESEARCH"]["primary"].web_search)
        self.assertFalse(self.policy["routes"]["DIRECT"]["primary"].web_search)
        self.assertEqual(
            "workspace-write",
            self.policy["routes"]["PROJECT"]["primary"].sandbox,
        )

    def test_direct_uses_luna_router_then_terra_executor_and_saves_trace(self):
        engine = FakeEngine([route_result(), execution_result()])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = OS.run_request(
                "캐시가 무엇인지 설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="direct",
            )
            for name in ("request.txt", "goal_ledger.json", "route.json", "result.md"):
                self.assertTrue((run_dir / name).is_file(), name)
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-terra"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertEqual("completed", payload["execution"]["status"])
        self.assertEqual(2, len(route_record["run"]["engine_trace"]))
        self.assertIn("model:gpt-5.6-terra", payload["execution"]["capabilities_used"])

    def test_context_is_supplied_to_router_and_executor(self):
        engine = FakeEngine([route_result(), execution_result()])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = root / "context.md"
            context.write_text("고정 독자: 신규 입사자", encoding="utf-8")
            OS.run_request(
                "안내문을 작성해 줘.",
                context_path=context,
                output_root=root / "runs",
                engine=engine,
                model_policy=self.policy,
                run_id="context",
            )
        self.assertEqual(2, len(engine.calls))
        for call in engine.calls:
            self.assertIn("고정 독자: 신규 입사자", call["prompt"])
            self.assertIn(str(context.resolve()), call["prompt"])

    def test_router_reserves_direct_for_requests_without_file_changes(self):
        prompt = OS.build_router_prompt(
            "receipt_probe.txt를 만들어 줘.",
            "",
            None,
            OS.EngineCapabilities(True, False, True, True, "fixture"),
        )

        self.assertIn("파일 시스템 변경 없이", prompt)
        self.assertIn("작업 규모가 작아도 DIRECT가 아니라 CODE", prompt)

    def test_router_retries_with_sol_when_luna_output_is_invalid(self):
        engine = FakeEngine([{}, route_result(), execution_result()])
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "요청",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="router-fallback",
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertEqual("rejected", payload["run"]["orchestration_trace"][0]["outcome"])
        self.assertEqual("accepted", payload["run"]["orchestration_trace"][1]["outcome"])

    def test_router_rejects_pipeline_rules_disguised_as_user_constraints(self):
        contaminated = route_result()
        contaminated["goal_ledger"]["fixed_constraints"].append(
            "이 단계에서는 설명문 자체를 생성하지 않는다."
        )
        engine = FakeEngine([contaminated, route_result(), execution_result()])
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "캐시를 설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="contaminated-router",
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertEqual("completed", payload["execution"]["status"])

    def test_direct_retries_with_sol_when_terra_output_is_invalid(self):
        engine = FakeEngine([route_result(), {}, execution_result()])
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="direct-fallback",
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertEqual("completed", payload["execution"]["status"])

    def test_direct_meta_answer_escalates_to_sol(self):
        deferred = execution_result(
            result="DIRECT 경로가 적절합니다. 외곽 실행 단계에서 작성하면 됩니다."
        )
        engine = FakeEngine([route_result(), deferred, execution_result()])
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="direct-meta-fallback",
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertEqual("실제로 생성된 결과입니다.", payload["execution"]["result_markdown"])

    def test_research_without_search_blocks_before_executor(self):
        capabilities = OS.EngineCapabilities(True, False, True, False, "disabled")
        engine = FakeEngine([route_result("RESEARCH")], capabilities)
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "오늘 노트북 가격을 조사해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="research-blocked",
            )
        self.assertEqual(1, len(engine.calls))
        self.assertEqual("blocked_by_capability", payload["execution"]["status"])
        self.assertEqual("live web search", payload["execution"]["needed_capability"])

    def test_reuse_requires_evidence_and_escalates_from_terra_to_sol(self):
        no_evidence = execution_result()
        with_evidence = execution_result(
            evidence=[
                {
                    "source": "template.md",
                    "finding": "기존 템플릿 확인",
                    "kind": "local",
                }
            ]
        )
        engine = FakeEngine([route_result("REUSE"), no_evidence, with_evidence])
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "기존 템플릿을 찾아 적용해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="reuse-fallback",
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertTrue(payload["execution"]["evidence"])

    def test_hybrid_runs_route_models_in_sequence_and_passes_primary_result(self):
        research = execution_result(
            result="공식 조사 결과",
            limitations=["조사 단계의 기준일 한계"],
            evidence=[
                {
                    "source": "https://example.test/official",
                    "finding": "최신 정보 확인",
                    "kind": "web",
                }
            ],
        )
        prompt = execution_result(
            result="반복 프롬프트 후보",
            limitations=["최종 프롬프트에 남은 한계"],
        )
        engine = FakeEngine(
            [
                route_result("HYBRID", primary="RESEARCH", secondary="PROMPT"),
                research,
                prompt,
            ]
        )
        compiled = {
            "final_prompt": "기존 Compiler 최종 결과",
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
                run_dir, payload = OS.run_request(
                    "조사 후 반복 프롬프트를 만들어 줘.",
                    output_root=Path(temp_dir),
                    engine=engine,
                    model_policy=self.policy,
                    run_id="hybrid",
                )
            compiler_context = run_dir / "prompt-compiler-context.md"
            self.assertIn(
                "공식 조사 결과",
                compiler_context.read_text(encoding="utf-8"),
            )
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-sol"],
            [call["invocation"].profile.model for call in engine.calls],
        )
        self.assertIn("공식 조사 결과", engine.calls[2]["prompt"])
        self.assertIn("기존 Compiler 최종 결과", engine.calls[2]["prompt"])
        self.assertEqual("반복 프롬프트 후보", payload["execution"]["result_markdown"])
        self.assertEqual(
            ["최종 프롬프트에 남은 한계"],
            payload["execution"]["limitations"],
        )
        self.assertEqual(
            "baseline_before_prompt_model",
            payload["prompt_compiler"]["application"],
        )

    def test_single_prompt_uses_existing_compiler_baseline_then_sol(self):
        engine = FakeEngine(
            [route_result("PROMPT"), execution_result(result="전용 모델 후보")]
        )
        compiled = {
            "final_prompt": "기존 Compiler 결과",
            "selected_mode": "pattern-only",
            "selection_reason": "구조화 필요",
            "used_patterns": ["Structured Output / Extraction"],
            "used_active_sources": [],
            "fallback": False,
            "fallback_reason": "",
        }
        runtime = mock.Mock()
        runtime.create_prompt.return_value = compiled
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(OS, "load_prompt_runtime", return_value=runtime):
                _, payload = OS.run_request(
                    "반복 지침을 만들어 줘.",
                    output_root=Path(temp_dir),
                    engine=engine,
                    model_policy=self.policy,
                    run_id="prompt",
                )
        self.assertEqual("gpt-5.6-sol", engine.calls[1]["invocation"].profile.model)
        self.assertIn("기존 Compiler 결과", engine.calls[1]["prompt"])
        self.assertEqual("전용 모델 후보", payload["execution"]["result_markdown"])
        runtime.create_prompt.assert_called_once()

    def test_write_claim_is_rejected_when_workspace_write_is_not_allowed(self):
        write_claim = execution_result(
            artifacts=[
                {
                    "path": "example.py",
                    "action": "modified",
                    "verification": "claimed",
                }
            ]
        )
        engine = FakeEngine([route_result("CODE"), write_claim])
        with tempfile.TemporaryDirectory() as temp_dir:
            _, payload = OS.run_request(
                "파일 자동화를 구현해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="write-claim",
            )
        self.assertEqual("blocked_by_capability", payload["execution"]["status"])
        self.assertIn("쓰기 capability", payload["execution"]["limitations"][0])

    def test_workspace_receipt_verifies_claimed_create_and_modify(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            existing = workspace / "existing.txt"
            existing.write_text("before", encoding="utf-8")
            before = OS.workspace_snapshot(workspace)

            existing.write_text("after", encoding="utf-8")
            (workspace / "created.txt").write_text("new", encoding="utf-8")
            after = OS.workspace_snapshot(workspace)
            receipt = OS.build_workspace_receipt(
                workspace,
                before,
                after,
                [
                    {
                        "path": "existing.txt",
                        "action": "modified",
                        "verification": "fixture",
                    },
                    {
                        "path": "created.txt",
                        "action": "created",
                        "verification": "fixture",
                    },
                ],
            )

        self.assertTrue(receipt["verified"])
        self.assertEqual(["created.txt"], receipt["actual_changes"]["created"])
        self.assertEqual(["existing.txt"], receipt["actual_changes"]["modified"])
        self.assertEqual([], receipt["issues"])

    def test_workspace_receipt_rejects_false_unreported_and_deleted_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            deleted = workspace / "deleted.txt"
            deleted.write_text("remove me", encoding="utf-8")
            before = OS.workspace_snapshot(workspace)

            deleted.unlink()
            (workspace / "unreported.txt").write_text("surprise", encoding="utf-8")
            after = OS.workspace_snapshot(workspace)
            receipt = OS.build_workspace_receipt(
                workspace,
                before,
                after,
                [
                    {
                        "path": "claimed.txt",
                        "action": "created",
                        "verification": "fixture",
                    }
                ],
            )

        self.assertFalse(receipt["verified"])
        self.assertTrue(
            any("일치하지 않습니다" in issue for issue in receipt["issues"])
        )
        self.assertTrue(
            any("기록되지 않은 파일 변화" in issue for issue in receipt["issues"])
        )
        self.assertTrue(any("파일 삭제" in issue for issue in receipt["issues"]))

    def test_workspace_snapshot_excludes_run_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            run_dir = workspace / "runs" / "fixture"
            run_dir.mkdir(parents=True)
            (workspace / "source.txt").write_text("keep", encoding="utf-8")
            (run_dir / "model-output.json").write_text("{}", encoding="utf-8")

            snapshot = OS.workspace_snapshot(workspace, excluded_root=run_dir)

        self.assertIn("source.txt", snapshot)
        self.assertNotIn("runs/fixture/model-output.json", snapshot)

    def test_workspace_write_snapshot_includes_gitignored_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / ".gitignore").write_text(
                "local-secret.txt\n",
                encoding="utf-8",
            )
            (workspace / "local-secret.txt").write_text(
                "before",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "init", "-q"],
                cwd=workspace,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            ordinary = OS.workspace_snapshot(workspace)
            write_snapshot = OS.workspace_snapshot(
                workspace,
                include_ignored=True,
            )

        self.assertNotIn("local-secret.txt", ordinary)
        self.assertIn("local-secret.txt", write_snapshot)

    def test_workspace_receipt_rejects_claim_outside_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            receipt = OS.build_workspace_receipt(
                workspace,
                {},
                {},
                [
                    {
                        "path": str(workspace.parent / "outside.txt"),
                        "action": "created",
                        "verification": "fixture",
                    }
                ],
            )

        self.assertFalse(receipt["verified"])
        self.assertTrue(
            any("작업공간 밖" in issue for issue in receipt["issues"])
        )

    def test_normalize_write_scopes_rejects_broad_protected_and_external_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            normalized = OS.normalize_write_scopes(
                workspace,
                ["web/app.js", "docs"],
            )
            with self.assertRaises(OS.ProblemSolvingError):
                OS.normalize_write_scopes(workspace, ["."])
            with self.assertRaises(OS.ProblemSolvingError):
                OS.normalize_write_scopes(workspace, [".git/config"])
            with self.assertRaises(OS.ProblemSolvingError):
                OS.normalize_write_scopes(workspace, ["runs/new"])
            with self.assertRaises(OS.ProblemSolvingError):
                OS.normalize_write_scopes(workspace, ["../outside"])

        self.assertEqual(["web/app.js", "docs"], normalized)

    def test_workspace_receipt_rejects_change_outside_approved_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            receipt = OS.build_workspace_receipt(
                workspace,
                {},
                {
                    "web/app.js": {"sha256": "one", "size": 1},
                    "README.md": {"sha256": "two", "size": 2},
                },
                [
                    {
                        "path": "web/app.js",
                        "action": "created",
                        "verification": "fixture",
                    },
                    {
                        "path": "README.md",
                        "action": "created",
                        "verification": "fixture",
                    },
                ],
                allowed_write_paths=["web"],
            )

        self.assertFalse(receipt["verified"])
        self.assertEqual(["web"], receipt["approved_write_paths"])
        self.assertTrue(
            any("exceeded the approved" in issue for issue in receipt["issues"])
        )

    def test_workspace_backup_restores_modified_deleted_and_created_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            existing = workspace / "existing.txt"
            deleted = workspace / "deleted.txt"
            existing.write_text("before", encoding="utf-8")
            deleted.write_text("keep", encoding="utf-8")
            before = OS.workspace_snapshot(workspace)
            backup = OS.backup_workspace_files(
                workspace,
                before,
                root / "backup",
            )

            existing.write_text("after", encoding="utf-8")
            deleted.unlink()
            created = workspace / "created.txt"
            created.write_text("new", encoding="utf-8")
            after = OS.workspace_snapshot(workspace)
            rollback = OS.restore_workspace(
                workspace,
                before,
                after,
                backup,
            )

            restored_existing = existing.read_text(encoding="utf-8")
            restored_deleted = deleted.read_text(encoding="utf-8")
            created_exists = created.exists()

        self.assertTrue(rollback["restored"])
        self.assertEqual("before", restored_existing)
        self.assertEqual("keep", restored_deleted)
        self.assertFalse(created_exists)

    def test_reuse_receipt_fingerprints_existing_file_and_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "template.md").write_text("template", encoding="utf-8")
            guide_dir = workspace / "guides"
            guide_dir.mkdir()
            (guide_dir / "guide.md").write_text("guide", encoding="utf-8")

            receipt = OS.build_reuse_receipt(
                workspace,
                [
                    {
                        "source": "template.md",
                        "finding": "중복 구조 작성을 막음",
                        "kind": "local",
                    }
                ],
                [
                    {
                        "path": "guides",
                        "action": "inspected",
                        "verification": "가이드 구조 확인",
                    }
                ],
            )

        self.assertTrue(receipt["verified"])
        self.assertEqual(["guides", "template.md"], [
            asset["path"] for asset in receipt["assets"]
        ])
        self.assertEqual("directory", receipt["assets"][0]["kind"])
        self.assertEqual(1, receipt["assets"][0]["file_count"])
        self.assertEqual("file", receipt["assets"][1]["kind"])

    def test_reuse_receipt_rejects_missing_and_external_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            receipt = OS.build_reuse_receipt(
                workspace,
                [
                    {
                        "source": "missing.md",
                        "finding": "존재한다고 주장",
                        "kind": "local",
                    },
                    {
                        "source": str(workspace.parent / "outside.md"),
                        "finding": "외부 자산 주장",
                        "kind": "local",
                    },
                ],
                [],
            )

        self.assertFalse(receipt["verified"])
        self.assertTrue(any("존재하지 않습니다" in item for item in receipt["issues"]))
        self.assertTrue(any("작업공간 밖" in item for item in receipt["issues"]))
        self.assertTrue(any("검증된 REUSE 자산" in item for item in receipt["issues"]))

    def test_reuse_directory_fingerprint_rejects_overly_broad_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "one.md").write_text("1", encoding="utf-8")
            (directory / "two.md").write_text("2", encoding="utf-8")

            with self.assertRaises(OS.ProblemSolvingError):
                OS.asset_fingerprint(directory, max_directory_files=1)

    def test_codex_engine_saves_verified_reuse_receipt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "template.md").write_text("verified", encoding="utf-8")
            run_dir = workspace / "runs" / "reuse-fixture"
            run_dir.mkdir(parents=True)
            engine = OS.CodexEngine(workspace)
            engine._executable = "codex"
            engine._capabilities = OS.EngineCapabilities(
                True, False, True, False, "fixture"
            )
            invocation = OS.InvocationSpec(
                name="primary-reuse",
                phase="executor",
                route="REUSE",
                profile=OS.ModelProfile(
                    "gpt-5.6-terra", "medium", False, "read-only"
                ),
                schema_path=OS.EXECUTION_SCHEMA_PATH,
            )
            output_path = run_dir / "primary-reuse-output.json"
            model_payload = execution_result(
                evidence=[
                    {
                        "source": "template.md",
                        "finding": "기존 구조를 재사용",
                        "kind": "local",
                    }
                ]
            )

            def fake_codex_run(*args, **kwargs):
                output_path.write_text(
                    json.dumps(model_payload, ensure_ascii=False),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="")

            with mock.patch.object(OS.subprocess, "run", side_effect=fake_codex_run):
                payload = engine.execute("inspect asset", run_dir, invocation)

            receipt = json.loads(
                (run_dir / "primary-reuse-reuse-receipt.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(model_payload, payload)
        self.assertTrue(receipt["verified"])
        self.assertEqual("template.md", receipt["assets"][0]["path"])
        self.assertTrue(engine.trace()[0]["reuse_receipt_verified"])

    def test_codex_engine_rejects_completed_reuse_with_missing_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            run_dir = workspace / "runs" / "missing-reuse"
            run_dir.mkdir(parents=True)
            engine = OS.CodexEngine(workspace)
            engine._executable = "codex"
            engine._capabilities = OS.EngineCapabilities(
                True, False, True, False, "fixture"
            )
            invocation = OS.InvocationSpec(
                name="primary-reuse",
                phase="executor",
                route="REUSE",
                profile=OS.ModelProfile(
                    "gpt-5.6-terra", "medium", False, "read-only"
                ),
                schema_path=OS.EXECUTION_SCHEMA_PATH,
            )
            output_path = run_dir / "primary-reuse-output.json"
            model_payload = execution_result(
                evidence=[
                    {
                        "source": "missing.md",
                        "finding": "없는 자산 주장",
                        "kind": "local",
                    }
                ]
            )

            def fake_codex_run(*args, **kwargs):
                output_path.write_text(
                    json.dumps(model_payload, ensure_ascii=False),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="")

            with mock.patch.object(OS.subprocess, "run", side_effect=fake_codex_run):
                with self.assertRaises(OS.ProblemSolvingError):
                    engine.execute("inspect missing asset", run_dir, invocation)

            receipt = json.loads(
                (run_dir / "primary-reuse-reuse-receipt.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertFalse(receipt["verified"])
        self.assertEqual("reuse_receipt_failed", engine.trace()[0]["status"])

    def test_codex_engine_saves_verified_workspace_receipt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            run_dir = workspace / "runs" / "fixture"
            run_dir.mkdir(parents=True)
            engine = OS.CodexEngine(workspace, allow_workspace_write=True)
            engine._executable = "codex"
            engine._capabilities = OS.EngineCapabilities(
                True, False, True, True, "fixture"
            )
            invocation = OS.InvocationSpec(
                name="primary-code",
                phase="executor",
                route="CODE",
                profile=OS.ModelProfile(
                    "gpt-5.6-sol", "high", False, "workspace-write"
                ),
                schema_path=OS.EXECUTION_SCHEMA_PATH,
            )
            output_path = run_dir / "primary-code-output.json"
            model_payload = execution_result(
                artifacts=[
                    {
                        "path": "created.txt",
                        "action": "created",
                        "verification": "fixture",
                    }
                ]
            )
            commands = []

            def fake_codex_run(*args, **kwargs):
                commands.append(args[0])
                output_path.write_text(
                    json.dumps(model_payload, ensure_ascii=False),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="")

            with mock.patch.object(
                OS,
                "workspace_snapshot",
                side_effect=[
                    {},
                    {"created.txt": {"sha256": "abc", "size": 3}},
                ],
            ), mock.patch.object(OS.subprocess, "run", side_effect=fake_codex_run):
                payload = engine.execute("create file", run_dir, invocation)

            receipt = json.loads(
                (run_dir / "primary-code-workspace-receipt.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(model_payload, payload)
        self.assertTrue(receipt["verified"])
        self.assertTrue(engine.trace()[0]["workspace_receipt_verified"])
        self.assertIn("--skip-git-repo-check", commands[-1])

    def test_codex_engine_rolls_back_change_outside_approved_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "existing.txt").write_text("before", encoding="utf-8")
            run_dir = workspace / "runs" / "scope-violation"
            run_dir.mkdir(parents=True)
            approval = {
                "approval_id": "approval-fixture",
                "approved_write_paths": ["allowed.txt"],
            }
            engine = OS.CodexEngine(
                workspace,
                allow_workspace_write=True,
                allowed_write_paths=["allowed.txt"],
                write_approval=approval,
            )
            engine._executable = "codex"
            engine._capabilities = OS.EngineCapabilities(
                True, False, True, True, "fixture"
            )
            invocation = OS.InvocationSpec(
                name="primary-code",
                phase="executor",
                route="CODE",
                profile=OS.ModelProfile(
                    "gpt-5.6-sol", "high", False, "workspace-write"
                ),
                schema_path=OS.EXECUTION_SCHEMA_PATH,
            )
            output_path = run_dir / "primary-code-output.json"
            model_payload = execution_result(
                artifacts=[
                    {
                        "path": "outside.txt",
                        "action": "created",
                        "verification": "fixture",
                    }
                ]
            )
            real_subprocess_run = OS.subprocess.run

            def fake_codex_run(*args, **kwargs):
                if args[0][0] == "git":
                    return real_subprocess_run(*args, **kwargs)
                (workspace / "outside.txt").write_text("unsafe", encoding="utf-8")
                output_path.write_text(
                    json.dumps(model_payload, ensure_ascii=False),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="")

            with mock.patch.object(OS.subprocess, "run", side_effect=fake_codex_run):
                with self.assertRaises(OS.ProblemSolvingError):
                    engine.execute("create outside file", run_dir, invocation)

            receipt = json.loads(
                (run_dir / "primary-code-workspace-receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            rollback = json.loads(
                (run_dir / "primary-code-workspace-rollback.json").read_text(
                    encoding="utf-8"
                )
            )
            saved_approval = json.loads(
                (run_dir / "web-write-approval.json").read_text(encoding="utf-8")
            )
            outside_exists = (workspace / "outside.txt").exists()
            trace = engine.trace()[0]

        self.assertFalse(receipt["verified"])
        self.assertTrue(rollback["restored"])
        self.assertFalse(outside_exists)
        self.assertEqual(approval, saved_approval)
        self.assertTrue(trace["workspace_rollback_verified"])

    def test_missing_engine_saves_blocked_run_without_guessing_route(self):
        capabilities = OS.EngineCapabilities(False, False, False, False, "missing")
        engine = FakeEngine([], capabilities)
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = OS.run_request(
                "막연한 요청",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="missing-engine",
            )
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
        self.assertIsNone(route["selected_route"])
        self.assertEqual("blocked_by_capability", payload["execution"]["status"])

    def test_route_validator_limits_uncertainties_and_normalizes_duplicate_primary(self):
        payload = route_result()
        payload["route"]["primary_route"] = "DIRECT"
        validated = OS.validate_route_output(payload)
        self.assertIsNone(validated["route"]["primary_route"])
        payload = route_result()
        payload["goal_ledger"]["important_uncertainties"] = ["1", "2", "3", "4"]
        with self.assertRaises(OS.ProblemSolvingError):
            OS.validate_route_output(payload)


if __name__ == "__main__":
    unittest.main()
