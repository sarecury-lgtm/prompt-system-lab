# Prompt Compiler Knowledge Bundle

This is the approved built-in runtime snapshot. The JSON block is data, not user instructions.

```json
{
  "bundle_version": "0.3-draft",
  "usage": "Default local knowledge for Prompt Compiler. Use without an Action call. GitHub Action is only for an explicit user-requested refresh.",
  "catalog": {
    "runtime_version": "0.3-draft",
    "kind": "prompt-compiler-catalog",
    "source_of_truth": {
      "patterns": "prompt-corpus/PATTERN_LESSONS_INDEX.md",
      "active": "specs/experiments/prompt-mode-contribution/active-source-policies.json",
      "protocol": "runtime/protocols/global-response-v3.1.json"
    },
    "routing_policy": {
      "baseline_first": true,
      "pattern_only_preferred": true,
      "full_corpus_auto_search": false,
      "max_active_sources_per_request": 1,
      "active_requires_unique_contribution": true,
      "fallback_order": [
        "active",
        "pattern-only",
        "baseline"
      ]
    },
    "patterns": [
      {
        "id": "role-task-frame",
        "name": "Role + task frame",
        "use_when": "The prompt is vague and needs a clear work mode",
        "reusable_move": "You are [role]. Your task is [objective]. Use [constraints]. Return [output shape].",
        "main_risk": "Decorative roleplay without success criteria",
        "asset": "runtime/patterns/role-task-frame.json"
      },
      {
        "id": "interface-emulation",
        "name": "Interface emulation",
        "use_when": "You want the model to simulate a tool or UI surface",
        "reusable_move": "Return simulated [tool/interface] output only; do not claim real execution.",
        "main_risk": "Fake execution results that look real",
        "asset": "runtime/patterns/interface-emulation.json"
      },
      {
        "id": "prompt-improvement-loop",
        "name": "Prompt improvement loop",
        "use_when": "You want to improve a weak prompt before using it",
        "reusable_move": "Diagnose missing control points → rewrite the prompt → name what changed.",
        "main_risk": "Polished but overcomplicated prompt that drifts from the real goal",
        "asset": "runtime/patterns/prompt-improvement-loop.json"
      },
      {
        "id": "defensive-jailbreak-analysis",
        "name": "Defensive jailbreak analysis",
        "use_when": "You are studying adversarial prompts safely",
        "reusable_move": "Classify the attack mechanism; do not reproduce runnable jailbreak text.",
        "main_risk": "Accidentally storing or improving unsafe operational text",
        "asset": "runtime/patterns/defensive-jailbreak-analysis.json"
      },
      {
        "id": "grounded-research",
        "name": "Grounded research",
        "use_when": "The answer depends on external/current sources",
        "reusable_move": "Search/inspect sources → cite claims → mark unknowns → separate recommendation from evidence.",
        "main_risk": "Confident synthesis from weak or stale sources",
        "asset": "runtime/patterns/grounded-research.json"
      },
      {
        "id": "structured-output-extraction",
        "name": "Structured output / extraction",
        "use_when": "The output must be parsed, compared, or reused",
        "reusable_move": "Define fields, null policy, evidence rule, and exact output shape.",
        "main_risk": "Pretty formatting without enforceable schema",
        "asset": "runtime/patterns/structured-output-extraction.json"
      },
      {
        "id": "evaluation-rubric",
        "name": "Evaluation rubric",
        "use_when": "You need to judge prompt/output quality consistently",
        "reusable_move": "Define criteria, scoring anchors, pass/fail rules, and failure examples.",
        "main_risk": "Vague “quality” judgment that cannot catch regressions",
        "asset": "runtime/patterns/evaluation-rubric.json"
      },
      {
        "id": "persistent-project-instruction",
        "name": "Persistent project instruction",
        "use_when": "The prompt should control ongoing assistant behavior",
        "reusable_move": "Define trigger, default behavior, boundaries, routing, and fallback.",
        "main_risk": "Rule pile with no priority or trigger",
        "asset": "runtime/patterns/persistent-project-instruction.json"
      },
      {
        "id": "coding-agent-workflow",
        "name": "Coding-agent workflow",
        "use_when": "The model works inside files, repos, tools, or code tasks",
        "reusable_move": "Inspect context → make smallest safe change → validate → summarize diff.",
        "main_risk": "Tool-using agent edits too much or skips validation",
        "asset": "runtime/patterns/coding-agent-workflow.json"
      }
    ],
    "active_sources": [
      {
        "source_id": "PR002",
        "task_types": [
          "텍스트 기반 도구·콘솔·인터페이스 시뮬레이션용 프롬프트 설계"
        ],
        "required_request_signals": [
          "실제 실행이 아닌 시뮬레이션이어야 함",
          "일반 명령 입력과 강사·운영자·메타 지시를 같은 대화에서 구분해야 함"
        ],
        "do_not_apply": [
          "실제 셸이나 서버에서 명령을 실행해야 하는 작업",
          "입력 채널이 하나뿐이고 메타 지시 구분이 필요 없는 단순 출력 요청"
        ],
        "unique_behavior": "명시된 메타 채널만 별도 처리하고 나머지 입력은 모의 인터페이스 입력으로 처리하는 폐쇄형 입력 문법을 정의한다.",
        "asset": "runtime/active/pr002.json"
      },
      {
        "source_id": "PR026",
        "task_types": [
          "탈옥·적대적 프롬프트·안전 사고의 방어적 분류와 회귀 시험 설계"
        ],
        "required_request_signals": [
          "공격 또는 안전 사고 기록을 분류·체계화하려는 목적",
          "공격 문구를 복원하거나 개선하지 않는 방어적·비운영적 경계"
        ],
        "do_not_apply": [
          "탈옥 문구를 강화·복원·우회하는 요청",
          "안전 사고 분류나 거절 품질 검증과 무관한 일반 보안 작업"
        ],
        "unique_behavior": "모델군, 공격 의도, 지시 압박 방식, 요청된 정책 우회를 별도 비운영적 필드로 기록한다.",
        "asset": "runtime/active/pr026.json"
      },
      {
        "source_id": "PR065",
        "task_types": [
          "반복 가능하고 기계 실행 가능한 평가·벤치마크·회귀 실험 설계"
        ],
        "required_request_signals": [
          "모델·프롬프트·조건을 반복 또는 버전별로 비교함",
          "사례·기대 결과·사람 판정·독립 평가 중 하나 이상의 평가 근거가 있음",
          "자동 실행기·CI·평가 파이프라인 같은 재현 가능한 실행 산출물이 필요함"
        ],
        "do_not_apply": [
          "답변 하나를 일회성으로 검토하거나 점수만 매기는 작업",
          "실행 가능한 평가 자료나 반복 비교가 필요 없는 일반 조언"
        ],
        "unique_behavior": "입력과 이상 행동을 담은 구조화 사례, 버전된 eval 단위, 채점 템플릿, 사람 라벨 기반 모델 평가자 검증을 구성한다.",
        "asset": "runtime/active/pr065.json"
      },
      {
        "source_id": "PR086",
        "task_types": [
          "Cursor 저장소의 범위별 지속 규칙 파일 설계"
        ],
        "required_request_signals": [
          "Cursor용 프로젝트·저장소 규칙이 필요함",
          "디렉터리·파일 유형·프레임워크별로 서로 다른 규칙을 적용해야 함"
        ],
        "do_not_apply": [
          "Cursor가 아닌 도구의 일반 프로젝트 지침",
          "한 번만 수행하는 단일 코딩 작업"
        ],
        "unique_behavior": "저장소 지침을 프로젝트 영역별 `.cursor/rules/*.mdc` 파일로 분리하고 각 파일의 적용 범위를 정의한다.",
        "asset": "runtime/active/pr086.json"
      },
      {
        "source_id": "PR089",
        "task_types": [
          "여러 코딩 작업 유형을 서로 다른 도구·파일 권한으로 수행하는 저장소 에이전트 운영 설계"
        ],
        "required_request_signals": [
          "하나의 코딩 에이전트가 조사·설계·구현·디버그·문서화 중 여러 유형을 처리함",
          "작업 유형에 따라 읽기·편집·명령·외부 도구 또는 파일 범위 권한이 달라짐",
          "사용자 대신 시스템이 가장 좁은 작업 모드를 선택해야 함"
        ],
        "do_not_apply": [
          "한 번의 일반 코딩 작업",
          "도구·파일 권한 차이가 없는 단순 분류나 프롬프트 모드 선택"
        ],
        "unique_behavior": "각 작업 모드에 역할, 활성 조건, 허용 도구 그룹, 파일 패턴, 금지 행동을 부여하고 가장 좁은 모드로 라우팅한다.",
        "asset": "runtime/active/pr089.json"
      },
      {
        "source_id": "PR091",
        "task_types": [
          "승인된 파일만 대상으로 후속 자동 적용기가 처리할 결정적 코드 패치 프롬프트 설계"
        ],
        "required_request_signals": [
          "참고용 읽기 전용 파일과 편집 승인 파일이 구분됨",
          "모델의 수정안을 후속 도구가 자동 적용함",
          "비슷한 코드 조각 때문에 잘못된 위치가 수정될 위험이 있음"
        ],
        "do_not_apply": [
          "현재 에이전트가 파일을 직접 편집하는 일반 저장소 작업",
          "자동 적용기나 정확 일치 패치 계약이 필요 없는 코드 리뷰"
        ],
        "unique_behavior": "편집 승인 파일에만 정확한 old/new 텍스트와 고유 문맥을 가진 결정적 패치를 내고 생략 기호와 placeholder를 금지한다.",
        "asset": "runtime/active/pr091.json"
      },
      {
        "source_id": "PR093",
        "task_types": [
          "요구사항에서 실행 가능한 다중 파일 애플리케이션·서비스를 생성하거나 불완전한 프로젝트를 완성하는 작업"
        ],
        "required_request_signals": [
          "여러 파일·진입점·의존성·파일 간 계약을 함께 맞춰야 함",
          "빈 함수·누락 파일·의존성 누락 같은 완전성 위험이 있음",
          "실행 모델이 저장소 편집과 검증 도구를 사용할 수 있음"
        ],
        "do_not_apply": [
          "단일 파일 또는 한 줄짜리 작은 수정",
          "파일·도구를 사용할 수 없는 설명 작업"
        ],
        "unique_behavior": "핵심 코드 단위를 먼저 식별하고 진입점에서 import·의존성을 따라가며 완전한 파일과 파일 간 계약을 검증한다.",
        "asset": "runtime/active/pr093.json"
      }
    ],
    "global_protocol": {
      "id": "global-response-protocol",
      "version": "3.1-reference",
      "role": "final goal-preservation and correction check; not a task pattern",
      "asset": "runtime/protocols/global-response-v3.1.json"
    }
  },
  "pattern_cards": [
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "role-task-frame",
      "name": "Role + task frame",
      "use_when": "The prompt is vague and needs a clear work mode",
      "reusable_move": "You are [role]. Your task is [objective]. Use [constraints]. Return [output shape].",
      "source_entries": "PR001",
      "main_risk": "Decorative roleplay without success criteria",
      "detail_markdown": "**Best for**\n\n- weak prompts like “analyze this” or “make this better”\n- writing, review, planning, explanation, and coaching prompts\n- turning casual requests into usable instruction surfaces\n\n**Core move**\n\n```text\nYou are [practical role].\nYour task is [specific objective].\nUse [context and constraints].\nReturn [specific output shape].\n```\n\n**Why it works**\n\nThe role narrows the response style, but the task and output contract do the real control work.\n\n**Do not overuse**\n\nAvoid empty prestige roles like “world-class expert” unless the prompt also defines what expert behavior means.\n\n**Related source entries**\n\n- PR001 — Awesome ChatGPT Prompts",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "interface-emulation",
      "name": "Interface emulation",
      "use_when": "You want the model to simulate a tool or UI surface",
      "reusable_move": "Return simulated [tool/interface] output only; do not claim real execution.",
      "source_entries": "PR002",
      "main_risk": "Fake execution results that look real",
      "detail_markdown": "**Best for**\n\n- mock terminal examples\n- simulated console output\n- teaching command/result concepts\n- UI behavior sketches\n\n**Core move**\n\n```text\nSimulate [interface].\nReturn only the simulated output surface.\nDo not claim that commands, code, tools, or external systems actually ran.\n```\n\n**Why it works**\n\nThe prompt limits the assistant to one narrow response channel.\n\n**Do not overuse**\n\nNever treat simulated output as evidence. Real execution needs a real tool.\n\n**Related source entries**\n\n- PR002 — Act as Linux Terminal\n- PR005 — Act as JavaScript Console\n- PR006 — Act as Excel Sheet",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "prompt-improvement-loop",
      "name": "Prompt improvement loop",
      "use_when": "You want to improve a weak prompt before using it",
      "reusable_move": "Diagnose missing control points → rewrite the prompt → name what changed.",
      "source_entries": "PR011; PR036, PR106, PR111 (partial/adjacent)",
      "main_risk": "Polished but overcomplicated prompt that drifts from the real goal",
      "detail_markdown": "**Best for**\n\n- rewriting messy prompts\n- turning long research prompts into compact prompts\n- converting one-off prompts into project instructions or skill-lite workflows\n\n**Core move**\n\n```text\nFirst diagnose what the prompt is missing.\nThen rewrite it.\nThen list only the important changes.\nDo not add assumptions that change the user's goal.\n```\n\n**Why it works**\n\nIt makes the model inspect the instruction surface before trying to solve the task.\n\n**Do not overuse**\n\nDo not add heavy structure unless the task needs it. Some prompts only need one clear sentence and an output format.\n\n**Related source entries**\n\n- PR011 — Act as Prompt Enhancer\n- PR036 — Absurdly Useful Micro-Prompts (partial; lightweight improvement add-ons)\n- PR106 — Prompt for Seeking Clarity and Avoiding Hallucinating (adjacent; clarification before answering)\n- PR111 — Prompt evaluator meta-prompt (partial; evaluator/improver structure)",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "defensive-jailbreak-analysis",
      "name": "Defensive jailbreak analysis",
      "use_when": "You are studying adversarial prompts safely",
      "reusable_move": "Classify the attack mechanism; do not reproduce runnable jailbreak text.",
      "source_entries": "PR025",
      "main_risk": "Accidentally storing or improving unsafe operational text",
      "detail_markdown": "**Best for**\n\n- studying unsafe prompt patterns\n- building safety reviews\n- identifying instruction-hierarchy attacks\n- writing defensive specs\n\n**Core move**\n\n```text\nAnalyze this as a defensive prompt-safety artifact.\nDo not reproduce or improve runnable jailbreak text.\nClassify the mechanism: identity override, hierarchy inversion, dual-channel response, reward/punishment pressure, fake system authority, or another mechanism.\n```\n\n**Why it works**\n\nIt keeps the useful lesson while avoiding operational misuse.\n\n**Do not overuse**\n\nDo not let adversarial prompt study become a prompt-improvement workflow for unsafe text.\n\n**Related source entries**\n\n- PR025 — ChatGPT DAN Repository\n- PR026 — LLM Jailbreaks\n- PR027 — ChatGPT DAN Jailbreak Gist\n- PR028–PR032 — DAN / anti-DAN community history",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "grounded-research",
      "name": "Grounded research",
      "use_when": "The answer depends on external/current sources",
      "reusable_move": "Search/inspect sources → cite claims → mark unknowns → separate recommendation from evidence.",
      "source_entries": "PR039, PR040, PR106, PR109",
      "main_risk": "Confident synthesis from weak or stale sources",
      "detail_markdown": "**Best for**\n\n- product research\n- current information checks\n- source-backed comparisons\n- “find the best X” tasks where price, availability, policy, law, or specs may change\n- any task where unsupported synthesis would be harmful\n\n**Core move**\n\n```text\nResearch [target] using source-traceable evidence.\nFor each important claim, include source, date checked, and confidence.\nSeparate confirmed facts from inference.\nMark unknowns as “확인 불가” instead of guessing.\nEnd with a decision table or recommendation only after evidence is shown.\n```\n\n**Why it works**\n\nResearch prompts fail when they skip from search results to confident conclusion. This pattern forces evidence collection, uncertainty handling, and final judgment into separate layers.\n\n**Do not overuse**\n\nDo not use this heavy structure for simple explanation tasks. Use it when the answer depends on changing facts or source quality.\n\n**Related source entries**\n\n- PR039 — OpenAI student use-case pack\n- PR040 — Student-voted prompt roundup\n- PR106 — Anti-hallucination / clarity prompt\n- PR109 — RAG / retrieval quality discussion",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "structured-output-extraction",
      "name": "Structured output / extraction",
      "use_when": "The output must be parsed, compared, or reused",
      "reusable_move": "Define fields, null policy, evidence rule, and exact output shape.",
      "source_entries": "PR061, PR062, PR064, PR106",
      "main_risk": "Pretty formatting without enforceable schema",
      "detail_markdown": "**Best for**\n\n- extracting fields from documents\n- turning messy text into JSON, tables, or checklists\n- classification tasks\n- comparison tables\n- workflows where another tool or human will reuse the output\n\n**Core move**\n\n```text\nExtract only the requested fields.\nUse this exact output shape: [schema/table/fields].\nIf a value is missing, return null or an empty list.\nInclude evidence text when the task depends on source grounding.\nOutput no extra commentary unless requested.\n```\n\n**Why it works**\n\nThe model has less room to invent structure when fields, missing-value policy, and evidence rules are fixed. This also makes downstream review easier.\n\n**Do not overuse**\n\nDo not force strict JSON when the user needs judgment, nuance, or explanation. Use structured output where consistency matters more than prose quality.\n\n**Related source entries**\n\n- PR061 — Anthropic Prompt Library\n- PR062 — Anthropic Prompt Engineering Overview\n- PR064 — OpenAI Prompt Examples / Cookbook\n- PR106 — Prompt for Seeking Clarity and Avoiding Hallucinating",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "evaluation-rubric",
      "name": "Evaluation rubric",
      "use_when": "You need to judge prompt/output quality consistently",
      "reusable_move": "Define criteria, scoring anchors, pass/fail rules, and failure examples.",
      "source_entries": "PR108, PR109, PR110, PR118",
      "main_risk": "Vague “quality” judgment that cannot catch regressions",
      "detail_markdown": "**Best for**\n\n- judging prompt quality\n- comparing two prompts or two outputs\n- checking whether a skill is working\n- reviewing model answers consistently across examples\n- building manual specs before automation exists\n\n**Core move**\n\n```text\nEvaluate [artifact] against these criteria:\n1. [criterion]\n2. [criterion]\n3. [criterion]\n\nFor each criterion, use anchors:\n- pass: [observable behavior]\n- partial: [borderline behavior]\n- fail: [failure behavior]\n\nReturn verdict, strongest part, weakest part, and one next edit.\n```\n\n**Why it works**\n\nRubrics turn vague taste into repeatable judgment. Anchors matter more than scores because they tell the reviewer what concrete behavior counts as success or failure.\n\n**Do not overuse**\n\nDo not create a giant scoring grid when the decision only needs one clear weakness and one fix.\n\n**Related source entries**\n\n- PR108 — Prompt Breaks AI Pattern-Matching in Real Time\n- PR109 — RAG / hallucination-control claim\n- PR110 — How to Evaluate the Quality of a Prompt\n- PR118 — Tools for Prompt Management and Testing",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "persistent-project-instruction",
      "name": "Persistent project instruction",
      "use_when": "The prompt should control ongoing assistant behavior",
      "reusable_move": "Define trigger, default behavior, boundaries, routing, and fallback.",
      "source_entries": "PR120, PR122; PR114-PR116 (indirect workflow/versioning support)",
      "main_risk": "Rule pile with no priority or trigger",
      "detail_markdown": "**Best for**\n\n- ChatGPT Projects\n- Custom GPT instructions\n- Claude Project instructions\n- assistant-wide behavior rules\n- recurring user preferences\n- repo-level Codex operating instructions\n\n**Core move**\n\n```text\n# Purpose\nThis instruction applies when [trigger/context].\n\n# Behavior\n- Prioritize [priority].\n- Do [default behavior].\n- Avoid [bad behavior].\n\n# Routing\n- If input is [type A], do [workflow A].\n- If input is [type B], do [workflow B].\n\n# Output\nReturn [fields/style].\n\n# Boundaries\nIf information is missing, [fallback].\n```\n\n**Why it works**\n\nPersistent instructions need triggers and priority more than one-off prompts do. Without them, they become a pile of preferences that may not activate at the right time.\n\n**Do not overuse**\n\nDo not put temporary task requirements into project instructions. Keep persistent rules stable and reusable.\n\n**Related source entries**\n\n- PR120 — ChatGPT Project custom-instruction discussion\n- PR122 — System-prompt archive metadata\n- PR114 — Prompt workflow/versioning discussion (indirect)\n- PR115 — Complex prompt workflow discussion (indirect)\n- PR116 — Prompt versioning and management discussion (indirect)",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "pattern-card",
      "id": "coding-agent-workflow",
      "name": "Coding-agent workflow",
      "use_when": "The model works inside files, repos, tools, or code tasks",
      "reusable_move": "Inspect context → make smallest safe change → validate → summarize diff.",
      "source_entries": "PR088, PR091; PR086, PR087, PR090, PR093 (partial); PR089, PR092 (indirect)",
      "main_risk": "Tool-using agent edits too much or skips validation",
      "detail_markdown": "**Best for**\n\n- repo editing\n- file refactoring\n- debugging\n- PR creation\n- Codex-style tasks\n- tool-using assistant workflows\n\n**Core move**\n\n```text\nInspect the relevant files first.\nMake the smallest safe change that solves the task.\nDo not make unrelated refactors.\nRun tests or checks if available.\nIf tests are unavailable, say what was checked instead.\nSummarize changed files and next action.\nAsk before destructive changes.\n```\n\n**Why it works**\n\nCoding agents fail by editing too much, skipping context, or claiming validation they did not run. This pattern constrains scope and forces a verifiable end state.\n\n**Do not overuse**\n\nDo not use a full repo-agent workflow for simple code snippets. Use it when files, tools, or project state matter.\n\n**Related source entries**\n\n- PR088 — Cline System Prompt Lineage\n- PR091 — Aider Coding Prompts\n- PR086 — Cursor Rules / `.cursorrules` Pattern (partial)\n- PR087 — Cursor Directory Rules (partial)\n- PR090 — Open Interpreter System Prompt Lineage (partial)\n- PR093 — GPT Engineer Prompt Lineage (partial)\n- PR089 — Roo Code / Roo-Code Agent Prompts (indirect)\n- PR092 — Continue.dev Prompt Templates (indirect)",
      "instruction": "Use this card as a design constraint. Write a new task-specific prompt; do not paste the reusable move unchanged unless it is already specific."
    }
  ],
  "active_cards": [
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR002",
        "task_types": [
          "텍스트 기반 도구·콘솔·인터페이스 시뮬레이션용 프롬프트 설계"
        ],
        "required_request_signals": [
          "실제 실행이 아닌 시뮬레이션이어야 함",
          "일반 명령 입력과 강사·운영자·메타 지시를 같은 대화에서 구분해야 함"
        ],
        "do_not_apply": [
          "실제 셸이나 서버에서 명령을 실행해야 하는 작업",
          "입력 채널이 하나뿐이고 메타 지시 구분이 필요 없는 단순 출력 요청"
        ],
        "unique_behavior": "명시된 메타 채널만 별도 처리하고 나머지 입력은 모의 인터페이스 입력으로 처리하는 폐쇄형 입력 문법을 정의한다.",
        "required_prompt_changes": [
          "허용 입력 유형과 판별 규칙이 명시된다.",
          "인터페이스 출력과 메타 응답 채널이 분리된다.",
          "실제 실행으로 오해시키는 표현이 금지된다."
        ],
        "fallback": "입력 문법과 메타 채널이 최종 프롬프트에 모두 나타나지 않으면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "simulate",
            "simulation",
            "interface emulator",
            "terminal simulator",
            "mock console",
            "시뮬레이션",
            "가상 콘솔",
            "모의 콘솔",
            "터미널 시뮬레이션",
            "인터페이스 시뮬레이션"
          ],
          "required_all": [
            {
              "id": "multi_channel",
              "any": [
                "instructor",
                "operator note",
                "meta instruction",
                "same chat",
                "강사",
                "운영자 지시",
                "메타 지시",
                "같은 대화"
              ]
            },
            {
              "id": "protocol_boundary",
              "any": [
                "command",
                "input type",
                "input grammar",
                "output channel",
                "명령",
                "입력 유형",
                "입력 구분",
                "출력 채널"
              ]
            }
          ],
          "exclude_any": [
            "actual shell",
            "execute on server",
            "run the command",
            "실제 셸",
            "실제 서버에서 실행",
            "실제 명령 실행"
          ],
          "requires_runtime_tools": false
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR026",
        "task_types": [
          "탈옥·적대적 프롬프트·안전 사고의 방어적 분류와 회귀 시험 설계"
        ],
        "required_request_signals": [
          "공격 또는 안전 사고 기록을 분류·체계화하려는 목적",
          "공격 문구를 복원하거나 개선하지 않는 방어적·비운영적 경계"
        ],
        "do_not_apply": [
          "탈옥 문구를 강화·복원·우회하는 요청",
          "안전 사고 분류나 거절 품질 검증과 무관한 일반 보안 작업"
        ],
        "unique_behavior": "모델군, 공격 의도, 지시 압박 방식, 요청된 정책 우회를 별도 비운영적 필드로 기록한다.",
        "required_prompt_changes": [
          "세분화된 안전 분류 필드가 산출물에 추가된다.",
          "원문 공격 문구 보존·복원 금지가 명시된다.",
          "분류 결과가 안전한 거절 품질 시험과 연결된다."
        ],
        "fallback": "세분화된 분류 필드가 없거나 공격 문구를 운영 가능한 형태로 보존하면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "jailbreak incident",
            "adversarial prompt",
            "safety incident",
            "refusal quality",
            "탈옥 사고",
            "적대적 프롬프트",
            "안전 사고",
            "거절 품질"
          ],
          "required_all": [
            {
              "id": "defensive_analysis",
              "any": [
                "classify",
                "taxonomy",
                "triage",
                "regression test",
                "분류",
                "체계화",
                "회귀 시험",
                "안전 평가"
              ]
            },
            {
              "id": "non_operational",
              "any": [
                "do not reproduce",
                "non-operational",
                "redacted",
                "masked",
                "복원하지",
                "비운영적",
                "마스킹",
                "재현 금지"
              ]
            }
          ],
          "exclude_any": [
            "make the jailbreak stronger",
            "improve the jailbreak",
            "bypass safety",
            "탈옥 강화",
            "더 강한 탈옥",
            "우회 방법",
            "안전 규칙을 우회"
          ],
          "requires_runtime_tools": false
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR065",
        "task_types": [
          "반복 가능하고 기계 실행 가능한 평가·벤치마크·회귀 실험 설계"
        ],
        "required_request_signals": [
          "모델·프롬프트·조건을 반복 또는 버전별로 비교함",
          "사례·기대 결과·사람 판정·독립 평가 중 하나 이상의 평가 근거가 있음",
          "자동 실행기·CI·평가 파이프라인 같은 재현 가능한 실행 산출물이 필요함"
        ],
        "do_not_apply": [
          "답변 하나를 일회성으로 검토하거나 점수만 매기는 작업",
          "실행 가능한 평가 자료나 반복 비교가 필요 없는 일반 조언"
        ],
        "unique_behavior": "입력과 이상 행동을 담은 구조화 사례, 버전된 eval 단위, 채점 템플릿, 사람 라벨 기반 모델 평가자 검증을 구성한다.",
        "required_prompt_changes": [
          "평가 데이터 파일과 버전 식별자가 산출물에 포함된다.",
          "자동 채점 형식과 파싱 가능한 판정 계약이 포함된다.",
          "모델 평가자를 사람 판정으로 교정·검증하는 절차가 포함된다."
        ],
        "fallback": "실행 가능한 평가 패키지나 사람 라벨 기반 평가자 검증이 최종 프롬프트에 나타나지 않으면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "evaluation harness",
            "eval pipeline",
            "evaluation experiment",
            "benchmark experiment",
            "regression evaluation",
            "performance experiment",
            "holdout validation",
            "평가 실행기",
            "평가 파이프라인",
            "평가 실험",
            "본 실험",
            "벤치마크 실험",
            "회귀 평가",
            "성능 실험",
            "비교 실험",
            "holdout 검증"
          ],
          "required_all": [
            {
              "id": "repeat_or_version",
              "any": [
                "repeat",
                "reproducible",
                "version",
                "regression",
                "conditions",
                "반복",
                "재현",
                "버전",
                "회귀",
                "조건별"
              ]
            },
            {
              "id": "evaluation_evidence",
              "any": [
                "test cases",
                "reference answers",
                "human labels",
                "independent evaluator",
                "blind evaluation",
                "사례",
                "모범 답변",
                "사람 판정",
                "독립 평가",
                "블라인드 평가",
                "평가 기준"
              ]
            },
            {
              "id": "machine_process",
              "any": [
                "automate",
                "runner",
                "pipeline",
                "CI",
                "machine-runnable",
                "run the experiment",
                "execute the experiment",
                "actual results",
                "자동",
                "실행기",
                "파이프라인",
                "실험을 실행",
                "본 실험을 실행",
                "실제 결과",
                "CI"
              ]
            }
          ],
          "exclude_any": [
            "one-time review",
            "single answer score",
            "답변 하나 평가",
            "일회성 검토"
          ],
          "requires_runtime_tools": false
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR086",
        "task_types": [
          "Cursor 저장소의 범위별 지속 규칙 파일 설계"
        ],
        "required_request_signals": [
          "Cursor용 프로젝트·저장소 규칙이 필요함",
          "디렉터리·파일 유형·프레임워크별로 서로 다른 규칙을 적용해야 함"
        ],
        "do_not_apply": [
          "Cursor가 아닌 도구의 일반 프로젝트 지침",
          "한 번만 수행하는 단일 코딩 작업"
        ],
        "unique_behavior": "저장소 지침을 프로젝트 영역별 `.cursor/rules/*.mdc` 파일로 분리하고 각 파일의 적용 범위를 정의한다.",
        "required_prompt_changes": [
          "생성할 `.mdc` 파일 목록과 경로가 제시된다.",
          "파일별 적용 디렉터리·파일 유형·프레임워크 범위가 제시된다.",
          "전역 규칙과 영역별 규칙의 충돌 처리 방식이 포함된다."
        ],
        "fallback": "Cursor의 범위별 `.mdc` 산출물로 구체화되지 않으면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "Cursor project rules",
            "Cursor repository rules",
            "Cursor rules",
            "Cursor 프로젝트 규칙",
            "Cursor 저장소 규칙",
            "커서 프로젝트 규칙"
          ],
          "required_all": [
            {
              "id": "persistent_configuration",
              "any": [
                "project rules",
                "repository rules",
                "persistent instruction",
                "프로젝트 규칙",
                "저장소 규칙",
                "지속 지침"
              ]
            },
            {
              "id": "scope_variance",
              "any": [
                "different directories",
                "file type",
                "framework",
                "monorepo",
                "디렉터리별",
                "파일 유형별",
                "프레임워크별",
                "모노레포"
              ]
            }
          ],
          "exclude_any": [
            "one-off",
            "single task",
            "일회성",
            "한 번만"
          ],
          "requires_runtime_tools": false
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR089",
        "task_types": [
          "여러 코딩 작업 유형을 서로 다른 도구·파일 권한으로 수행하는 저장소 에이전트 운영 설계"
        ],
        "required_request_signals": [
          "하나의 코딩 에이전트가 조사·설계·구현·디버그·문서화 중 여러 유형을 처리함",
          "작업 유형에 따라 읽기·편집·명령·외부 도구 또는 파일 범위 권한이 달라짐",
          "사용자 대신 시스템이 가장 좁은 작업 모드를 선택해야 함"
        ],
        "do_not_apply": [
          "한 번의 일반 코딩 작업",
          "도구·파일 권한 차이가 없는 단순 분류나 프롬프트 모드 선택"
        ],
        "unique_behavior": "각 작업 모드에 역할, 활성 조건, 허용 도구 그룹, 파일 패턴, 금지 행동을 부여하고 가장 좁은 모드로 라우팅한다.",
        "required_prompt_changes": [
          "모드별 권한 계약이 명시된다.",
          "모드 선택 조건과 전환·중단 조건이 명시된다.",
          "파일 범위와 금지 행동이 모드별로 달라진다."
        ],
        "fallback": "모드별 도구·파일 권한 계약이 최종 프롬프트에 없으면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "coding assistant",
            "repository assistant",
            "coding agent policy",
            "코딩 도우미",
            "저장소 도우미",
            "코딩 에이전트 운영"
          ],
          "required_all": [
            {
              "id": "multiple_work_types",
              "any": [
                "architecture",
                "investigation",
                "debug",
                "implementation",
                "documentation",
                "아키텍처",
                "조사",
                "디버그",
                "구현",
                "문서"
              ]
            },
            {
              "id": "permission_variance",
              "any": [
                "different permissions",
                "tool groups",
                "read edit command",
                "file patterns",
                "권한을 다르게",
                "도구 권한",
                "읽기 편집 명령",
                "파일 범위"
              ]
            },
            {
              "id": "automatic_routing",
              "any": [
                "route",
                "choose mode",
                "user need not specify",
                "라우팅",
                "모드 선택",
                "자동 선택"
              ]
            }
          ],
          "exclude_any": [
            "baseline",
            "pattern-only",
            "active",
            "full corpus",
            "프롬프트 모드",
            "전체 자료 모드",
            "활성 자료 모드"
          ],
          "requires_runtime_tools": false
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR091",
        "task_types": [
          "승인된 파일만 대상으로 후속 자동 적용기가 처리할 결정적 코드 패치 프롬프트 설계"
        ],
        "required_request_signals": [
          "참고용 읽기 전용 파일과 편집 승인 파일이 구분됨",
          "모델의 수정안을 후속 도구가 자동 적용함",
          "비슷한 코드 조각 때문에 잘못된 위치가 수정될 위험이 있음"
        ],
        "do_not_apply": [
          "현재 에이전트가 파일을 직접 편집하는 일반 저장소 작업",
          "자동 적용기나 정확 일치 패치 계약이 필요 없는 코드 리뷰"
        ],
        "unique_behavior": "편집 승인 파일에만 정확한 old/new 텍스트와 고유 문맥을 가진 결정적 패치를 내고 생략 기호와 placeholder를 금지한다.",
        "required_prompt_changes": [
          "읽기 전용 맥락과 편집 승인 목록의 권한 차이가 명시된다.",
          "정확히 한 위치와 일치하는 교체 원문이 요구된다.",
          "생략 기호·placeholder·모호한 패치가 금지된다."
        ],
        "fallback": "정확 일치 패치 문법이 없거나 일반 diff만 요구하면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "automatic patch applier",
            "machine-applied patch",
            "patch protocol",
            "자동 적용기",
            "기계 적용 패치",
            "패치 프로토콜"
          ],
          "required_all": [
            {
              "id": "edit_boundary",
              "any": [
                "approved files",
                "editable files",
                "read-only context",
                "승인 파일",
                "편집 허용",
                "읽기 전용"
              ]
            },
            {
              "id": "wrong_target_risk",
              "any": [
                "wrong location",
                "similar code",
                "exact match",
                "deterministic",
                "엉뚱한 위치",
                "비슷한 코드",
                "정확 일치",
                "결정적"
              ]
            },
            {
              "id": "downstream_application",
              "any": [
                "automatic applier",
                "machine apply",
                "downstream tool",
                "자동 적용기",
                "기계 적용",
                "후속 도구"
              ]
            }
          ],
          "exclude_any": [
            "edit the files directly",
            "apply the change yourself",
            "직접 파일 수정",
            "바로 구현"
          ],
          "requires_runtime_tools": false
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    },
    {
      "runtime_version": "0.3-draft",
      "kind": "active-source-card",
      "source": {
        "source_id": "PR093",
        "task_types": [
          "요구사항에서 실행 가능한 다중 파일 애플리케이션·서비스를 생성하거나 불완전한 프로젝트를 완성하는 작업"
        ],
        "required_request_signals": [
          "여러 파일·진입점·의존성·파일 간 계약을 함께 맞춰야 함",
          "빈 함수·누락 파일·의존성 누락 같은 완전성 위험이 있음",
          "실행 모델이 저장소 편집과 검증 도구를 사용할 수 있음"
        ],
        "do_not_apply": [
          "단일 파일 또는 한 줄짜리 작은 수정",
          "파일·도구를 사용할 수 없는 설명 작업"
        ],
        "unique_behavior": "핵심 코드 단위를 먼저 식별하고 진입점에서 import·의존성을 따라가며 완전한 파일과 파일 간 계약을 검증한다.",
        "required_prompt_changes": [
          "핵심 코드 단위와 진입점이 먼저 식별된다.",
          "import·의존성 추적이 구현·검증 순서에 포함된다.",
          "export, 환경 변수, API, 빌드 설정 등 파일 간 호환성 검사가 포함된다."
        ],
        "fallback": "진입점 기반 의존성 추적과 파일 간 호환성 검증이 최종 프롬프트에 없으면 pattern-only로 복귀한다.",
        "matching": {
          "task_type_any": [
            "multi-file code generation",
            "generate an application",
            "build a service",
            "complete an incomplete project",
            "다중 파일 생성",
            "애플리케이션 생성",
            "서비스 구현",
            "불완전한 프로젝트 완성"
          ],
          "required_all": [
            {
              "id": "cross_file_scope",
              "any": [
                "multiple files",
                "entrypoint",
                "dependencies",
                "cross-file",
                "imports",
                "여러 파일",
                "진입점",
                "의존성",
                "파일 간",
                "import"
              ]
            },
            {
              "id": "completeness_risk",
              "any": [
                "runnable",
                "incomplete",
                "stubs",
                "missing dependency",
                "실행 가능",
                "불완전",
                "빈 함수",
                "의존성 누락"
              ]
            }
          ],
          "exclude_any": [
            "single file",
            "one-line change",
            "minimal patch",
            "단일 파일",
            "한 줄 수정",
            "작은 패치"
          ],
          "requires_runtime_tools": true
        }
      },
      "global_policy": {
        "max_active_sources_per_request": 1,
        "full_corpus_auto_search": false,
        "fallback": "Discard this card and use pattern-only unless every matching condition is satisfied and its unique behavior appears in the final prompt."
      }
    }
  ],
  "global_protocol": {
    "id": "global-response-protocol",
    "version": "3.1-reference",
    "status": "evolving-reference",
    "purpose": "사용자의 문제를 바꾸지 않은 채 앞으로 나아가도록 최종 프롬프트를 검사한다.",
    "runtime_role": "이 문서는 작업 유형을 선택하는 패턴이 아니다. 선택된 패턴으로 작성한 최종 프롬프트가 사용자의 원래 목적, 정의, 관계, 순서, 범위, 조건, 산출물을 보존했는지 검사하는 공통 품질 계층이다.",
    "sequence": [
      {
        "stage": "복원",
        "checks": [
          "직접 질문과 실제 목적을 구분한다.",
          "판단·행동 대상, 제공 근거, 요구 산출물, 성공 조건을 복원한다.",
          "사용자가 요청하지 않은 더 익숙한 문제로 바꾸지 않는다."
        ]
      },
      {
        "stage": "잠금",
        "checks": [
          "사용자가 정한 용어와 정의를 보존한다.",
          "비교 대상, 평가 기준, 주체와 대상, 시간 순서를 보존한다.",
          "포함·제외 범위, 기존 기능, 출력 형태, 정정 내용을 보존한다."
        ]
      },
      {
        "stage": "발전",
        "checks": [
          "복원하고 잠근 범위 안에서만 근거, 후보, 구분, 설계, 판단을 추가한다.",
          "추가 내용이 원래 질문의 병목을 실제로 해결하는지 확인한다.",
          "결과물을 요청받았으면 설명으로 대체하지 않는다."
        ]
      },
      {
        "stage": "대조",
        "checks": [
          "사용자가 물은 질문과 최종 프롬프트가 해결하는 질문이 같은지 확인한다.",
          "정의, 관계, 순서, 범위, 필수 조건과 산출물이 유지됐는지 확인한다.",
          "미확인 사실이나 실행하지 않은 결과를 확정적으로 말하도록 요구하지 않는지 확인한다."
        ]
      }
    ],
    "correction_rule": "사용자가 정정하면 동의만 하지 말고 잘못 잡은 구분축을 고친 뒤, 정정 내용을 새 불변 조건으로 적용해 전체 프롬프트를 다시 맞춘다.",
    "uncertainty_rule": "확인됨, 추론, 미확인을 구분하고 정보 부족으로 결과가 크게 갈릴 때만 짧은 질문을 한다. 이미 답이 있는 질문은 다시 묻지 않는다.",
    "execution_truth_rule": "도구, 파일, 웹 또는 데이터에 접근할 수 없으면 접근한 것처럼 지시하거나 결과를 꾸미지 않는다. 가능한 범위, 실패, 미확인 범위를 구분한다.",
    "density_rule": "간단한 요청에는 최소 구조만 사용하고, 복잡한 요청에는 필요한 통제점만 추가한다. 내부 체크리스트를 최종 사용자용 프롬프트에 기계적으로 덤프하지 않는다.",
    "final_gate": [
      "원래 질문과 최종 프롬프트의 문제가 같다.",
      "정의, 관계, 순서, 범위가 유지됐다.",
      "요청한 산출물이 포함됐다.",
      "결론이나 요구가 근거보다 강하지 않다.",
      "추측을 사실처럼 만들지 않는다.",
      "추가 구조가 초점을 바꾸거나 결과물을 대신하지 않는다."
    ],
    "provenance": {
      "provided_file": "global_response_protocol_v3_1.md",
      "usage_note": "사용자가 계속 개선할 참고 자료로 제공했으며 고정된 최종 규칙으로 취급하지 않는다."
    }
  }
}
```
