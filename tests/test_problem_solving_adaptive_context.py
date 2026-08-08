import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_adaptive_context as CONTEXT
import problem_solving_os as OS


class FakeEngine:
    def __init__(self, response):
        self.response = response
        self.invocations = []

    def capabilities(self):
        return OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
        )

    def execute(self, prompt, run_dir, invocation):
        self.invocations.append(invocation.name)
        return self.response

    def trace(self):
        return []


def empty_response():
    return {
        "context_evidence": {
            "summary": "현재 구매 결정에 필요한 명시 조건만 보존한다.",
            "facts": [],
            "unresolved": [],
        }
    }


class AdaptiveContextTests(unittest.TestCase):
    def test_rejects_fabricated_source_quote(self):
        payload = {
            "context_evidence": {
                "summary": "요약",
                "facts": [
                    {
                        "id": "fact-1",
                        "category": "avoidance",
                        "statement": "템포크 제외",
                        "source_quote": "템포크는 절대 싫다",
                        "subject_terms": ["템포크"],
                        "must_preserve": True,
                    }
                ],
                "unresolved": [],
            }
        }
        with self.assertRaisesRegex(CONTEXT.AdaptiveContextError, "원문에 없는"):
            CONTEXT.validate_context_evidence(
                payload,
                "두꺼운 삼겹살을 선호한다.",
            )

    def test_rejects_subject_not_present_in_quote(self):
        payload = {
            "context_evidence": {
                "summary": "요약",
                "facts": [
                    {
                        "id": "fact-1",
                        "category": "avoidance",
                        "statement": "특정 상품 제외",
                        "source_quote": "이 제품은 별로였다",
                        "subject_terms": ["템포크"],
                        "must_preserve": True,
                    }
                ],
                "unresolved": [],
            }
        }
        with self.assertRaisesRegex(CONTEXT.AdaptiveContextError, "인용 안에 없는"):
            CONTEXT.validate_context_evidence(payload, "이 제품은 별로였다")

    def test_request_only_quote_is_dropped_before_context_validation(self):
        request = "온라인에서 살 수 있는 삼겹살 중 내 취향에 가장 맞는 제품을 조사해 줘."
        context = "두꺼운 삼겹살의 육즙과 식감을 중요하게 본다."
        response = {
            "context_evidence": {
                "summary": "관련 맥락만 사용한다.",
                "facts": [
                    {
                        "id": "request-echo",
                        "category": "goal",
                        "statement": "온라인 삼겹살 조사",
                        "source_quote": request,
                        "subject_terms": [],
                        "must_preserve": True,
                    },
                    {
                        "id": "context-fact",
                        "category": "preference",
                        "statement": "두꺼운 식감 선호",
                        "source_quote": context,
                        "subject_terms": [],
                        "must_preserve": True,
                    },
                ],
                "unresolved": [],
            }
        }
        engine = FakeEngine(response)
        profile = OS.ModelProfile(
            model="fake",
            reasoning_effort="low",
            web_search=False,
            sandbox="read-only",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = CONTEXT.extract_context_evidence(
                request,
                context,
                engine=engine,
                run_dir=Path(temp_dir),
                policy={"router_fallback": profile},
            )

        quotes = [fact["source_quote"] for fact in evidence["facts"]]
        self.assertNotIn(request, quotes)
        self.assertIn(context, quotes)

    def test_strong_prior_experience_is_preserved_when_model_omits_it(self):
        context = "템포크를 실제로 먹어봤는데 매우 별로였다.\n두꺼운 삼겹살을 선호한다."
        engine = FakeEngine(empty_response())
        profile = OS.ModelProfile(
            model="fake",
            reasoning_effort="low",
            web_search=False,
            sandbox="read-only",
        )
        policy = {"router_fallback": profile}
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = CONTEXT.extract_context_evidence(
                "온라인 삼겹살을 추천해 줘",
                context,
                engine=engine,
                run_dir=Path(temp_dir),
                policy=policy,
            )

        prior = next(
            fact
            for fact in evidence["facts"]
            if fact["category"] == "prior_experience"
        )
        self.assertEqual(
            "템포크를 실제로 먹어봤는데 매우 별로였다.",
            prior["source_quote"],
        )
        self.assertEqual(["템포크"], prior["subject_terms"])
        self.assertTrue(prior["must_preserve"])
        self.assertEqual(["adaptive-context-evidence"], engine.invocations)

    def test_empty_context_does_not_invoke_model(self):
        engine = FakeEngine(empty_response())
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = CONTEXT.extract_context_evidence(
                "상품 추천",
                "",
                engine=engine,
                run_dir=Path(temp_dir),
                policy={},
            )
        self.assertEqual([], evidence["facts"])
        self.assertEqual([], engine.invocations)


if __name__ == "__main__":
    unittest.main()
