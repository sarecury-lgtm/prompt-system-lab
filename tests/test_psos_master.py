import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "PSOS_MASTER.md"
BLUEPRINT = ROOT / "specs" / "PSOS_SYSTEM_BLUEPRINT.md"
POLICY = ROOT / "problem-solving-project" / "model-policy.json"


class PsosMasterTests(unittest.TestCase):
    def test_master_is_linked_from_entry_documents_and_blueprint(self):
        for path in (
            ROOT / "README.md",
            ROOT / "USAGE.md",
            BLUEPRINT,
        ):
            with self.subTest(path=path.name):
                self.assertIn(
                    "PSOS_MASTER.md",
                    path.read_text(encoding="utf-8"),
                )

    def test_master_covers_active_routes_models_and_canonical_files(self):
        text = MASTER.read_text(encoding="utf-8")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))

        for route in (*policy["routes"], "HYBRID"):
            with self.subTest(route=route):
                self.assertIn(f"`{route}`", text)
        models = {
            policy["router"]["model"],
            policy["router_fallback"]["model"],
            *(
                profile["primary"]["model"]
                for profile in policy["routes"].values()
            ),
        }
        for model in models:
            with self.subTest(model=model):
                self.assertIn(f"`{model}`", text)
        for relative in (
            "scripts/problem_solving_os.py",
            "scripts/problem_solving_web.py",
            "scripts/problem_solving_status.py",
            "problem-solving-project/model-policy.json",
            "schemas/problem-solving-os-route.schema.json",
            "schemas/problem-solving-os-execution.schema.json",
            "specs/PSOS_SYSTEM_BLUEPRINT.md",
        ):
            with self.subTest(path=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_master_contains_the_complete_causal_and_safety_summary(self):
        text = MASTER.read_text(encoding="utf-8")
        required_sections = (
            "## 2. 왜 만들었는가",
            "## 3. 어떤 목적 때문에 무엇을 만들었는가",
            "## 4. 결국 만들어진 것은 무엇인가",
            "## 5. 전체 구조",
            "## 10. 안전한 파일 변경 설계",
            "## 12. 학습과 정책 변경 설계",
            "## 14. 현재 구현 상태",
            "## 15. 현재 한계",
            "## 16. AI가 이 저장소를 읽는 순서",
            "## 20. 최종 요약",
        )

        for section in required_sections:
            with self.subTest(section=section):
                self.assertIn(section, text)
        for contract in (
            "모델은 경로·결과·파일 변경·정책 변경을 제안할 수 있지만",
            "untrusted claim",
            "scoped approval",
            "--write-scope",
            "cli-write-approval.json",
            "content-addressed backup",
            "실행 간 content-addressed 백업 v3",
            "백업 manifest v4",
            "빈 디렉터리 receipt·rollback",
            "기존 v2·v1 복구 호환성",
            "기존 v1 경로 복사 백업",
            "paired evaluation",
            "atomic apply/rollback",
            "사용자의 목적을 중심으로 판단·실행·검증·복구·학습을 연결한",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)


if __name__ == "__main__":
    unittest.main()
