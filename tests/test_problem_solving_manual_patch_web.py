import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_manual_patch_web.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_manual_patch_web", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = PATCH
SPEC.loader.exec_module(PATCH)


class ManualPatchManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = PATCH.ManualPatchManager(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_file_and_auto_compile(self):
        preview = self.manager.preview(
            {
                "request": "새 모듈을 만든다.",
                "allowed_write_paths": ["pkg"],
                "operations": [
                    {
                        "action": "create",
                        "path": "pkg/new_module.py",
                        "content": "VALUE = 3\n",
                    }
                ],
                "test_commands": [],
            }
        )
        self.assertEqual(preview["status"], "pending")
        self.assertIn("py_compile", preview["test_commands"][0])

        result = self.manager.execute(preview["patch_id"])

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["receipt"]["verified"])
        self.assertEqual((self.root / "pkg/new_module.py").read_text(), "VALUE = 3\n")
        self.assertEqual(result["receipt"]["actual_changes"]["created"], ["pkg/new_module.py"])

    def test_failed_compile_restores_replaced_file(self):
        target = self.root / "pkg/module.py"
        target.parent.mkdir(parents=True)
        target.write_text("VALUE = 1\n", encoding="utf-8")
        preview = self.manager.preview(
            {
                "request": "기존 모듈을 수정한다.",
                "allowed_write_paths": ["pkg/module.py"],
                "operations": [
                    {
                        "action": "replace",
                        "path": "pkg/module.py",
                        "content": "def broken(:\n",
                    }
                ],
            }
        )

        result = self.manager.execute(preview["patch_id"])

        self.assertEqual(result["status"], "rolled_back")
        self.assertTrue(result["rollback"]["restored"])
        self.assertEqual(target.read_text(encoding="utf-8"), "VALUE = 1\n")
        self.assertIn("검사 실패", result["error"])

    def test_out_of_scope_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "허용 경로 밖"):
            self.manager.preview(
                {
                    "allowed_write_paths": ["web"],
                    "operations": [
                        {
                            "action": "create",
                            "path": "scripts/unsafe.py",
                            "content": "x = 1\n",
                        }
                    ],
                }
            )

    def test_delete_and_shell_commands_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "삭제"):
            self.manager.preview(
                {
                    "allowed_write_paths": ["web"],
                    "operations": [
                        {"action": "delete", "path": "web/a.js", "content": ""}
                    ],
                }
            )
        with self.assertRaisesRegex(ValueError, "셸 연산자"):
            self.manager.preview(
                {
                    "allowed_write_paths": ["web"],
                    "operations": [
                        {"action": "create", "path": "web/a.js", "content": "const a = 1;\n"}
                    ],
                    "test_commands": ["node --check web/a.js && echo bad"],
                }
            )

    def test_preview_detects_stale_file_before_apply(self):
        target = self.root / "web/app.js"
        target.parent.mkdir(parents=True)
        target.write_text("const value = 1;\n", encoding="utf-8")
        preview = self.manager.preview(
            {
                "allowed_write_paths": ["web/app.js"],
                "operations": [
                    {
                        "action": "replace",
                        "path": "web/app.js",
                        "content": "const value = 2;\n",
                    }
                ],
            }
        )
        target.write_text("const value = 99;\n", encoding="utf-8")

        result = self.manager.execute(preview["patch_id"])

        self.assertEqual(result["status"], "rolled_back")
        self.assertIn("검토 이후 파일이 달라져", result["error"])
        self.assertEqual(target.read_text(encoding="utf-8"), "const value = 99;\n")


if __name__ == "__main__":
    unittest.main()
