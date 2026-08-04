import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_quality_next_loop_final_web.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_quality_next_loop_final_web_test",
    MODULE_PATH,
)
FINAL_WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = FINAL_WEB
SPEC.loader.exec_module(FINAL_WEB)


class FinalizingNextLoopWebTests(unittest.TestCase):
    def test_job_packet_script_loads_after_route_policy_before_manual_ui(self):
        addons = FINAL_WEB.build_static_addons()
        renderer = addons["renderer.js"]

        self.assertIn("next-loop-job-packet.js", renderer)
        self.assertLess(
            renderer.index("psos-manual-route-policy.js"),
            renderer.index("next-loop-job-packet.js"),
        )
        self.assertLess(
            renderer.index("next-loop-job-packet.js"),
            renderer.index("chatgpt-manual-fallback-v5.js"),
        )

    def test_start_script_uses_finalizing_launcher(self):
        script = (ROOT / "start-psos-next-loop.ps1").read_text(encoding="utf-8")
        self.assertIn("problem_solving_quality_next_loop_final_web.py", script)


if __name__ == "__main__":
    unittest.main()
