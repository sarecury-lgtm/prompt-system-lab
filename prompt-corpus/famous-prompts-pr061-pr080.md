# Famous Prompts — PR061–PR080

## Purpose

Continue the prompt corpus with official prompt libraries, prompt marketplaces, image-prompt communities, and widely referenced prompt frameworks.

## Seed Entries (PR061–PR080)

### PR061
- **ID:** PR061
- **Name:** Anthropic Prompt Library
- **Source URL:** https://docs.anthropic.com/en/prompt-library
- **Platform:** Anthropic Docs
- **Type:** official prompt library
- **Short excerpt:** Official Claude prompt examples across writing, analysis, coding, and productivity tasks.
- **Structure summary:** Task-oriented prompt examples framed as reusable recipes with clear role, context, and output expectations.
- **Evidence note:**
  - **Short excerpt or paraphrased structure:** Local entry describes official examples as reusable recipes with role, context, and output expectations.
  - **Reusable move:** Turn a task into a concrete recipe: define the job, provide context, and specify the expected output shape.
  - **Pattern connection:** Supports the Structured output / extraction lesson because reusable prompt examples become stronger when output expectations are explicit and reviewable.
  - **Verification limit:** Exact Anthropic example text was not verified from local repo content; this note uses the existing structure summary and avoids quoting long source text.
- **Why it matters:** Strong official source for studying Claude-style prompt tone and structure.
- **Tags:** `official`, `anthropic`, `claude`, `prompt-library`
- **Safety / reproduction note:** Prefer linking and summarizing examples rather than copying long prompt text.

### PR062
- **ID:** PR062
- **Name:** Anthropic Prompt Engineering Overview
- **Source URL:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview
- **Platform:** Anthropic Docs
- **Type:** official prompt guide
- **Short excerpt:** Guidance on clarity, examples, context, and structured prompting for Claude.
- **Structure summary:** Explains prompt design as a process of specifying task, context, constraints, examples, and output shape.
- **Why it matters:** Useful baseline for comparing Claude-style natural language prompting with ChatGPT-style project instructions.
- **Tags:** `official`, `claude`, `prompt-engineering`, `guide`
- **Safety / reproduction note:** Store as reference source; do not treat every Claude pattern as directly portable to other models.

### PR063
- **ID:** PR063
- **Name:** Anthropic Metaprompt / Prompt Generator
- **Source URL:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-generator
- **Platform:** Anthropic Docs
- **Type:** meta-prompt / prompt generation workflow
- **Short excerpt:** Official workflow for generating stronger prompts from user goals.
- **Structure summary:** Uses task description, examples, constraints, and output formatting to synthesize improved prompts.
- **Why it matters:** Important source for studying prompt-improver and prompt-builder patterns.
- **Tags:** `meta-prompt`, `prompt-generator`, `anthropic`, `official`
- **Safety / reproduction note:** Generated prompts still need testing; do not assume automatic prompt improvement is reliable.

### PR064
- **ID:** PR064
- **Name:** OpenAI Prompt Examples / Cookbook
- **Source URL:** https://cookbook.openai.com/
- **Platform:** OpenAI Cookbook
- **Type:** official examples and recipes
- **Short excerpt:** OpenAI examples for structured outputs, classification, extraction, retrieval, and assistant workflows.
- **Structure summary:** Recipe-style examples combining task framing, input data, output schema, and validation ideas.
- **Why it matters:** Official reference for practical prompt patterns in API and product workflows.
- **Tags:** `official`, `openai`, `cookbook`, `recipes`
- **Safety / reproduction note:** Keep examples updated with current model/API behavior.

### PR065
- **ID:** PR065
- **Name:** OpenAI Evals Prompting Examples
- **Source URL:** https://github.com/openai/evals
- **Platform:** GitHub / OpenAI
- **Type:** evaluation dataset and prompt examples
- **Short excerpt:** Open-source evaluation framework with examples of prompts and grading structures.
- **Structure summary:** Evaluation-focused prompt assets paired with test cases, metrics, and task definitions.
- **Why it matters:** Shows how prompts can be tied to tests instead of treated as one-off text.
- **Tags:** `evals`, `openai`, `testing`, `promptops`
- **Safety / reproduction note:** Eval prompts should be reviewed for task fit before reuse.

### PR066
- **ID:** PR066
- **Name:** Learn Prompting
- **Source URL:** https://learnprompting.org/
- **Platform:** Learn Prompting
- **Type:** prompt education site
- **Short excerpt:** Educational prompt examples covering basics, role prompting, few-shot, CoT, and applied prompting.
- **Structure summary:** Lesson-based prompt examples arranged by technique and difficulty.
- **Why it matters:** One of the most widely referenced public prompt-learning resources.
- **Tags:** `education`, `prompting`, `examples`, `techniques`
- **Safety / reproduction note:** Use as learning reference; verify older examples against current model behavior.

### PR067
- **ID:** PR067
- **Name:** Prompt Engineering Guide by DAIR.AI
- **Source URL:** https://www.promptingguide.ai/
- **Platform:** PromptingGuide.ai
- **Type:** prompt technique guide
- **Short excerpt:** Examples for zero-shot, few-shot, chain-of-thought, ReAct, self-consistency, and more.
- **Structure summary:** Technique-indexed guide that pairs explanations with example prompt patterns.
- **Why it matters:** Major reference hub for academic and practical prompt engineering techniques.
- **Tags:** `DAIR`, `techniques`, `CoT`, `ReAct`
- **Safety / reproduction note:** Treat as technique reference; test patterns before adopting them in workflows.

### PR068
- **ID:** PR068
- **Name:** PromptHero
- **Source URL:** https://prompthero.com/
- **Platform:** PromptHero
- **Type:** image prompt marketplace / library
- **Short excerpt:** Searchable library of image-generation prompts for Midjourney, Stable Diffusion, and related tools.
- **Structure summary:** Visual prompt entries combine generated image, model/tool metadata, and prompt text or prompt-like descriptors.
- **Why it matters:** Important source for studying image-prompt culture, style keywords, and visual prompt packaging.
- **Tags:** `image-prompt`, `prompt-marketplace`, `Midjourney`, `Stable-Diffusion`
- **Safety / reproduction note:** Respect licensing and avoid identity/deceptive image-generation misuse.

### PR069
- **ID:** PR069
- **Name:** PromptBase
- **Source URL:** https://promptbase.com/
- **Platform:** PromptBase
- **Type:** paid prompt marketplace
- **Short excerpt:** Marketplace where users buy and sell prompts for text and image models.
- **Structure summary:** Commercial prompt packaging with titles, previews, model targets, and sales-oriented descriptions.
- **Why it matters:** Shows how prompts became monetized products and how sellers frame prompt value.
- **Tags:** `marketplace`, `paid-prompts`, `commercial`, `prompt-economy`
- **Safety / reproduction note:** Do not copy paid prompt text; store only metadata and structural observations.

### PR070
- **ID:** PR070
- **Name:** AIPRM Prompt Templates
- **Source URL:** https://www.aiprm.com/prompts/
- **Platform:** AIPRM
- **Type:** prompt template marketplace / extension library
- **Short excerpt:** Large catalog of prompt templates for SEO, marketing, writing, development, and business tasks.
- **Structure summary:** Template library arranged by category, popularity, and user-facing prompt title.
- **Why it matters:** Major example of prompt templates becoming an extension-driven workflow layer.
- **Tags:** `AIPRM`, `templates`, `SEO`, `marketing`
- **Safety / reproduction note:** Treat templates as third-party content; check quality, spam risk, and outdated tactics.

### PR071
- **ID:** PR071
- **Name:** Snack Prompt
- **Source URL:** https://snackprompt.com/
- **Platform:** Snack Prompt
- **Type:** community prompt library
- **Short excerpt:** User-shared prompts organized like a browsable prompt discovery platform.
- **Structure summary:** Community library focused on discoverability, categories, and ready-to-run prompt snippets.
- **Why it matters:** Useful for studying non-GitHub prompt-sharing UX.
- **Tags:** `community`, `prompt-library`, `discovery`, `templates`
- **Safety / reproduction note:** Verify prompt source, safety, and usefulness before importing.

### PR072
- **ID:** PR072
- **Name:** PromptPal
- **Source URL:** https://www.promptpal.net/
- **Platform:** PromptPal
- **Type:** prompt marketplace / prompt library
- **Short excerpt:** Public prompt examples and marketplace-style prompt collections.
- **Structure summary:** Browseable prompt items with titles, use cases, and category labels.
- **Why it matters:** Another example of prompts packaged as searchable reusable assets.
- **Tags:** `marketplace`, `prompt-library`, `templates`, `discovery`
- **Safety / reproduction note:** Avoid copying proprietary prompt text; collect metadata and patterns.

### PR073
- **ID:** PR073
- **Name:** God Mode / AutoGPT Prompting Lineage
- **Source URL:** https://github.com/Significant-Gravitas/AutoGPT
- **Platform:** GitHub
- **Type:** autonomous agent prompt lineage
- **Short excerpt:** AutoGPT-style agents use goals, constraints, commands, and memory-like loops.
- **Structure summary:** Agent prompt pattern built around role, goals, constraints, commands/tools, and iterative task execution.
- **Why it matters:** Important bridge from one-shot prompts to autonomous agent/workflow prompts.
- **Tags:** `agent`, `AutoGPT`, `goals`, `tools`
- **Safety / reproduction note:** Agent prompts need strong boundaries, tool permissions, and human oversight.

### PR074
- **ID:** PR074
- **Name:** BabyAGI Prompt / Task Loop Lineage
- **Source URL:** https://github.com/yoheinakajima/babyagi
- **Platform:** GitHub
- **Type:** agent task-loop prompt lineage
- **Short excerpt:** Task creation, prioritization, and execution loops driven by LLM prompts.
- **Structure summary:** Breaks goals into task lists and repeatedly updates priorities based on results.
- **Why it matters:** Historical source for prompt-driven agent task management patterns.
- **Tags:** `agent`, `task-loop`, `BabyAGI`, `planning`
- **Safety / reproduction note:** Use only with bounded scope and explicit stop conditions.

### PR075
- **ID:** PR075
- **Name:** Microsoft Semantic Kernel Prompt Templates
- **Source URL:** https://github.com/microsoft/semantic-kernel
- **Platform:** GitHub / Microsoft
- **Type:** prompt template framework
- **Short excerpt:** Prompt templates and skills/functions used inside Semantic Kernel workflows.
- **Structure summary:** Prompts treated as reusable functions with variables, orchestration, and tool integration.
- **Why it matters:** Strong example of prompts as software components rather than isolated chat text.
- **Tags:** `semantic-kernel`, `prompt-functions`, `templates`, `orchestration`
- **Safety / reproduction note:** Validate templates in the target runtime and avoid leaking sensitive variables.

### PR076
- **ID:** PR076
- **Name:** LangChain Hub Prompts
- **Source URL:** https://smith.langchain.com/hub
- **Platform:** LangSmith / LangChain
- **Type:** prompt hub / prompt registry
- **Short excerpt:** Shared prompt templates for chains, agents, RAG, extraction, and evaluation workflows.
- **Structure summary:** Prompt registry pattern with reusable templates, variables, and versioned usage in chains.
- **Why it matters:** Important source for production-style prompt reuse and prompt registry design.
- **Tags:** `langchain`, `prompt-hub`, `registry`, `RAG`
- **Safety / reproduction note:** Check template age and compatibility with current models before use.

### PR077
- **ID:** PR077
- **Name:** LangChain Prompt Templates Documentation
- **Source URL:** https://python.langchain.com/docs/concepts/prompt_templates/
- **Platform:** LangChain Docs
- **Type:** prompt template documentation
- **Short excerpt:** Explains prompt templates as reusable parameterized instructions.
- **Structure summary:** Defines string/chat/message templates with input variables and composition patterns.
- **Why it matters:** Useful for turning personal prompts into reusable app-like components.
- **Tags:** `templates`, `langchain`, `variables`, `prompt-components`
- **Safety / reproduction note:** Be careful with untrusted variables and prompt injection in templated contexts.

### PR078
- **ID:** PR078
- **Name:** Midjourney Prompting Documentation
- **Source URL:** https://docs.midjourney.com/docs/prompts
- **Platform:** Midjourney Docs
- **Type:** official image prompt guide
- **Short excerpt:** Official guidance on text prompts, parameters, style words, and image prompting behavior.
- **Structure summary:** Image prompt format combines subject, style, medium, composition, and model parameters.
- **Why it matters:** Core source for understanding image prompt syntax and visual prompt design.
- **Tags:** `Midjourney`, `image-prompt`, `official`, `parameters`
- **Safety / reproduction note:** Follow platform rules and avoid impersonation/deceptive image prompts.

### PR079
- **ID:** PR079
- **Name:** Stable Diffusion Prompt Book
- **Source URL:** https://openart.ai/promptbook
- **Platform:** OpenArt
- **Type:** image prompt book
- **Short excerpt:** Prompting guide for Stable Diffusion-style image generation.
- **Structure summary:** Teaches prompt anatomy, modifiers, style keywords, negative prompts, and visual composition controls.
- **Why it matters:** Widely referenced image-prompt learning material.
- **Tags:** `Stable-Diffusion`, `image-prompt`, `negative-prompt`, `promptbook`
- **Safety / reproduction note:** Check current licensing and avoid unsafe image-generation use cases.

### PR080
- **ID:** PR080
- **Name:** Lexica Prompt Search
- **Source URL:** https://lexica.art/
- **Platform:** Lexica
- **Type:** image prompt search engine
- **Short excerpt:** Search engine for AI-generated images and associated prompt text.
- **Structure summary:** Image-first prompt corpus where visual results are linked to prompt phrases and style descriptors.
- **Why it matters:** Useful for studying real prompt-image pairs and visual style language.
- **Tags:** `image-prompt`, `search`, `Stable-Diffusion`, `visual-corpus`
- **Safety / reproduction note:** Respect image rights and avoid prompts targeting real-person identity misuse.
