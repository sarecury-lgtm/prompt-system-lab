# ChatGPT GitHub Runtime

This directory is the read-only runtime surface used by a Custom GPT Action.
The model runs inside the user's ChatGPT subscription; GitHub only serves the
approved routing and prompt-design assets. No OpenAI API key is used.

## Source boundaries

- Patterns come from `prompt-corpus/PATTERN_LESSONS_INDEX.md`.
- Active cards come from the seven entries in
  `specs/experiments/prompt-mode-contribution/active-source-policies.json`.
- `global-response-v3.1.json` is an evolving reference and final quality gate,
  not a new task pattern.
- Full-corpus automatic search remains disabled.

## Build

```powershell
python scripts/build_chatgpt_action_runtime.py
```

The generated files are deterministic. Run the repository tests after every
build. Paste `CUSTOM_GPT_INSTRUCTIONS.md` into the GPT Instructions field and
`openapi.yaml` into the GPT Action schema.

Do not call this runtime complete until the published GitHub assets have been
used successfully from the real Custom GPT interface.
