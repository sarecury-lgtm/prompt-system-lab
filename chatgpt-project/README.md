# ChatGPT Project Setup

This is the primary user-facing Prompt Compiler v0.2 surface. ChatGPT supplies the AI writing step; this Git repository remains the source of truth for the formula.

## Set up once

1. In ChatGPT, create a new Project named `Prompt Compiler`.
2. Open Project settings and paste the full contents of `PROMPT_COMPILER_INSTRUCTIONS.md` into Project instructions.
3. Add these three repository files as project sources:
   - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
   - `skills/prompt-design-workflow.md`
   - `specs/experiments/prompt-mode-contribution/active-source-policies.json`
4. Start a new chat in that Project and enter an ordinary-language request.

Example:

```text
세 개의 협업 도구를 조사해서 우리 팀에 맞는 것을 고르게 하는 프롬프트를 만들어줘. 가격, 보안, 도입 난이도를 비교하고 확인되지 않은 정보는 추정하지 않게 해줘.
```

ChatGPT should return a ready-to-copy prompt first, followed by a compact selection record. Copy the prompt into the AI product where the actual task will be performed.

## What updates Git

Using the ChatGPT Project does not edit this repository. Git changes only when the formula, policies, tests, or examples are intentionally updated through the repository workflow:

```text
edit with Codex → test → commit → push → pull request → merge
```

After a merged repository release changes one of the four Project files, manually replace the corresponding Project instruction or source file. Record the repository commit in the Project description if version tracking matters.

## Current limitations

- The ChatGPT Project follows the routing contract as instructions; it does not execute the local Python router.
- Uploaded project sources are a release snapshot, not an automatic two-way Git sync.
- The local `scripts/prompt_runtime.py` command remains the deterministic template fallback until the local AI backend is packaged and validated separately.
