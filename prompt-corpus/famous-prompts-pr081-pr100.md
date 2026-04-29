# Famous Prompts — PR081–PR100

## Purpose

Finish the first 100-entry seed corpus with prompt pattern libraries, agent prompt frameworks, coding-agent instruction sources, and widely referenced prompt/system-prompt repositories.

## Seed Entries (PR081–PR100)

### PR081
- **ID:** PR081
- **Name:** Fabric Patterns
- **Source URL:** https://github.com/danielmiessler/fabric
- **Platform:** GitHub
- **Type:** prompt pattern framework
- **Short excerpt:** Large library of reusable prompts called “patterns” for real-world tasks.
- **Structure summary:** Task-specific prompt files organized as reusable command-like patterns.
- **Why it matters:** One of the clearest examples of treating prompts as a reusable operating layer rather than one-off chat text.
- **Tags:** `fabric`, `patterns`, `prompt-library`, `workflow`
- **Safety / reproduction note:** Review each pattern before reuse; some patterns may assume specific tools or user intent.

### PR082
- **ID:** PR082
- **Name:** Fabric extract_wisdom Pattern
- **Source URL:** https://github.com/danielmiessler/fabric
- **Platform:** GitHub
- **Type:** extraction prompt pattern
- **Short excerpt:** Extracts insights, ideas, recommendations, and notable points from long content.
- **Structure summary:** Converts messy source material into structured wisdom/insight sections.
- **Why it matters:** Representative of practical content-mining prompts used for podcasts, videos, essays, and transcripts.
- **Tags:** `fabric`, `extraction`, `summarization`, `insights`
- **Safety / reproduction note:** Verify extracted claims against the source; extraction can still distort emphasis.

### PR083
- **ID:** PR083
- **Name:** Fabric summarize Pattern
- **Source URL:** https://github.com/danielmiessler/fabric
- **Platform:** GitHub
- **Type:** summarization prompt pattern
- **Short excerpt:** Produces compact structured summaries from longer input.
- **Structure summary:** Defines summary sections and forces the model to compress content into reusable notes.
- **Why it matters:** Good baseline for studying how prompt libraries standardize everyday summarization.
- **Tags:** `fabric`, `summary`, `notes`, `compression`
- **Safety / reproduction note:** Keep source citations or links when summaries are used for research.

### PR084
- **ID:** PR084
- **Name:** Fabric create_art_prompt Pattern
- **Source URL:** https://github.com/danielmiessler/fabric
- **Platform:** GitHub
- **Type:** image/art prompt generation pattern
- **Short excerpt:** Generates prompts for visual or artistic AI tools.
- **Structure summary:** Turns user intent into richer visual prompt language with style, medium, subject, and atmosphere.
- **Why it matters:** Shows crossover between text prompt libraries and image-prompt engineering.
- **Tags:** `fabric`, `image-prompt`, `art`, `creative`
- **Safety / reproduction note:** Avoid prompts designed to imitate living artists or real private individuals without consent.

### PR085
- **ID:** PR085
- **Name:** Fabric analyze_claims Pattern
- **Source URL:** https://github.com/danielmiessler/fabric
- **Platform:** GitHub
- **Type:** critical analysis prompt pattern
- **Short excerpt:** Identifies claims, assumptions, evidence, and weaknesses in an argument.
- **Structure summary:** Breaks input into claim-level units and evaluates support or reasoning quality.
- **Why it matters:** Useful reference for building debate, comment-analysis, and argument-inspection prompts.
- **Tags:** `fabric`, `argument-analysis`, `claims`, `critical-thinking`
- **Safety / reproduction note:** Separate source text from model inference to avoid overclaiming.

### PR086
- **ID:** PR086
- **Name:** Cursor Rules / .cursorrules Pattern
- **Source URL:** https://github.com/PatrickJS/awesome-cursorrules
- **Platform:** GitHub
- **Type:** coding assistant instruction collection
- **Short excerpt:** Project-level rules that guide Cursor’s behavior across a codebase.
- **Structure summary:** Persistent repo-local instructions for coding style, architecture, tests, and framework conventions.
- **Why it matters:** Important parallel to project instructions and Claude Skills for developer workflows.
- **Tags:** `cursor`, `rules`, `coding-agent`, `project-instructions`
- **Safety / reproduction note:** Keep rules specific; overly broad coding rules can cause brittle or noisy outputs.

### PR087
- **ID:** PR087
- **Name:** Cursor Directory Rules
- **Source URL:** https://cursor.directory/
- **Platform:** Cursor Directory
- **Type:** prompt/rule directory
- **Short excerpt:** Browseable examples of Cursor rules for different stacks and frameworks.
- **Structure summary:** Rules packaged by technology, project style, and coding convention.
- **Why it matters:** Shows how system/project prompts are shared as reusable developer assets.
- **Tags:** `cursor`, `rules-directory`, `developer`, `templates`
- **Safety / reproduction note:** Adapt rules to the actual repo; do not blindly import framework rules.

### PR088
- **ID:** PR088
- **Name:** Cline System Prompt Lineage
- **Source URL:** https://github.com/cline/cline
- **Platform:** GitHub
- **Type:** coding agent system prompt source
- **Short excerpt:** Coding-agent instructions for planning, editing files, using tools, and reporting results.
- **Structure summary:** Agent prompt built around tool use, stepwise coding work, constraints, and user confirmation points.
- **Why it matters:** Useful source for studying app-like AI workflows and tool-using assistant instructions.
- **Tags:** `cline`, `coding-agent`, `system-prompt`, `tools`
- **Safety / reproduction note:** Tool-using prompts need permission boundaries and file-change review.

### PR089
- **ID:** PR089
- **Name:** Roo Code / Roo-Code Agent Prompts
- **Source URL:** https://github.com/RooCodeInc/Roo-Code
- **Platform:** GitHub
- **Type:** coding agent prompt source
- **Short excerpt:** Agent instructions for coding modes, tool use, and project-aware development.
- **Structure summary:** Mode-based assistant behavior with different roles for coding, debugging, and task execution.
- **Why it matters:** Good example of multi-mode prompt design for software agents.
- **Tags:** `roo-code`, `coding-agent`, `modes`, `tool-use`
- **Safety / reproduction note:** Treat mode prompts as implementation-specific; test before adapting.

### PR090
- **ID:** PR090
- **Name:** Open Interpreter System Prompt Lineage
- **Source URL:** https://github.com/OpenInterpreter/open-interpreter
- **Platform:** GitHub
- **Type:** tool-using assistant prompt source
- **Short excerpt:** Prompts for an assistant that can operate a local interpreter-like environment.
- **Structure summary:** Combines natural language task handling with tool execution expectations and runtime feedback.
- **Why it matters:** Important bridge between chat prompts and executable local AI assistants.
- **Tags:** `open-interpreter`, `tools`, `local-agent`, `system-prompt`
- **Safety / reproduction note:** Local tool execution needs strong user approval and sandboxing.

### PR091
- **ID:** PR091
- **Name:** Aider Coding Prompts
- **Source URL:** https://github.com/Aider-AI/aider
- **Platform:** GitHub
- **Type:** coding assistant prompt source
- **Short excerpt:** Prompts and conventions for AI-assisted code editing through git-aware workflows.
- **Structure summary:** Coding instructions connected to repository context, diffs, edit format, and commit-aware changes.
- **Why it matters:** Strong example of prompt design integrated with version control and file editing.
- **Tags:** `aider`, `coding`, `git`, `code-editing`
- **Safety / reproduction note:** Review patches and tests; generated diffs can introduce subtle bugs.

### PR092
- **ID:** PR092
- **Name:** Continue.dev Prompt Templates
- **Source URL:** https://github.com/continuedev/continue
- **Platform:** GitHub
- **Type:** coding assistant prompt/config source
- **Short excerpt:** Configurable prompts and commands for codebase-aware AI assistance.
- **Structure summary:** Developer workflow prompts embedded into IDE assistant configuration and command templates.
- **Why it matters:** Useful example of prompts becoming part of IDE configuration.
- **Tags:** `continue`, `IDE`, `coding-assistant`, `templates`
- **Safety / reproduction note:** Keep project secrets out of prompt context and generated logs.

### PR093
- **ID:** PR093
- **Name:** GPT Engineer Prompt Lineage
- **Source URL:** https://github.com/AntonOsika/gpt-engineer
- **Platform:** GitHub
- **Type:** software-generation agent prompts
- **Short excerpt:** Prompts for generating code projects from natural language specs.
- **Structure summary:** Converts user requirements into clarifying questions, project plans, and generated code artifacts.
- **Why it matters:** Famous early example of prompting an LLM as a software project generator.
- **Tags:** `gpt-engineer`, `code-generation`, `agent`, `specs`
- **Safety / reproduction note:** Generated projects require security review, tests, and dependency checks.

### PR094
- **ID:** PR094
- **Name:** ChatDev Role Prompts
- **Source URL:** https://github.com/OpenBMB/ChatDev
- **Platform:** GitHub
- **Type:** multi-agent role prompt framework
- **Short excerpt:** Simulates a software company with role-based agents like CEO, CTO, programmer, and reviewer.
- **Structure summary:** Uses multiple specialized personas and communication phases to generate software.
- **Why it matters:** Important example of prompt-based multi-agent organization design.
- **Tags:** `multi-agent`, `roles`, `software-company`, `ChatDev`
- **Safety / reproduction note:** Role simulation can create plausible but low-quality work unless evaluated carefully.

### PR095
- **ID:** PR095
- **Name:** MetaGPT SOP Prompts
- **Source URL:** https://github.com/FoundationAgents/MetaGPT
- **Platform:** GitHub
- **Type:** multi-agent SOP prompt framework
- **Short excerpt:** Uses standard operating procedures and role prompts to coordinate agent work.
- **Structure summary:** Role-based agents follow structured workflows, documents, and handoffs.
- **Why it matters:** Strong source for studying prompt-as-process and document-driven agent coordination.
- **Tags:** `MetaGPT`, `SOP`, `multi-agent`, `workflow`
- **Safety / reproduction note:** Avoid assuming multi-agent outputs are more correct without external checks.

### PR096
- **ID:** PR096
- **Name:** Microsoft AutoGen Agent Prompts
- **Source URL:** https://github.com/microsoft/autogen
- **Platform:** GitHub / Microsoft
- **Type:** multi-agent conversation framework
- **Short excerpt:** Agent messages and system instructions for multi-agent task solving.
- **Structure summary:** Agents are configured with roles, tools, message routing, and conversation patterns.
- **Why it matters:** Major framework for studying how prompts control agent collaboration.
- **Tags:** `AutoGen`, `multi-agent`, `roles`, `conversation`
- **Safety / reproduction note:** Agent conversations need termination rules and human oversight.

### PR097
- **ID:** PR097
- **Name:** CrewAI Agent Role Prompts
- **Source URL:** https://github.com/crewAIInc/crewAI
- **Platform:** GitHub
- **Type:** role-based agent framework
- **Short excerpt:** Agents are configured by role, goal, backstory, tools, and task handoffs.
- **Structure summary:** Prompt-like role specs are packaged as reusable agent definitions in workflows.
- **Why it matters:** Useful example of persona prompting becoming structured agent configuration.
- **Tags:** `CrewAI`, `agents`, `roles`, `workflow`
- **Safety / reproduction note:** Backstory-heavy agent prompts should not replace task-specific instructions and validation.

### PR098
- **ID:** PR098
- **Name:** SuperAGI Agent Prompt Lineage
- **Source URL:** https://github.com/TransformerOptimus/SuperAGI
- **Platform:** GitHub
- **Type:** autonomous agent prompt framework
- **Short excerpt:** Autonomous agent framework with goals, tools, memory, and task execution loops.
- **Structure summary:** Prompted agent loop uses objectives, resource constraints, tool calls, and iterative planning.
- **Why it matters:** Historical source for autonomous-agent prompt architecture after AutoGPT.
- **Tags:** `SuperAGI`, `autonomous-agent`, `tools`, `planning`
- **Safety / reproduction note:** Autonomous agents need strict scoping and monitoring.

### PR099
- **ID:** PR099
- **Name:** CAMEL Role-Playing Agent Prompts
- **Source URL:** https://github.com/camel-ai/camel
- **Platform:** GitHub
- **Type:** role-playing multi-agent prompt framework
- **Short excerpt:** Role-playing agents communicate to solve tasks using assigned roles and instructions.
- **Structure summary:** Two or more agents are prompted with complementary roles to drive task-oriented dialogue.
- **Why it matters:** Important research/practice bridge for role-prompted multi-agent systems.
- **Tags:** `CAMEL`, `role-playing`, `multi-agent`, `research`
- **Safety / reproduction note:** Multi-agent agreement is not evidence of correctness; use external evaluation.

### PR100
- **ID:** PR100
- **Name:** Awesome GPT Prompts / Community Prompt Indexes
- **Source URL:** https://github.com/topics/chatgpt-prompts
- **Platform:** GitHub Topics
- **Type:** prompt corpus discovery index
- **Short excerpt:** Topic page collecting many ChatGPT prompt repositories and prompt packs.
- **Structure summary:** Meta-index for discovering prompt repositories by stars, recency, and topic labels.
- **Why it matters:** Closes the first corpus batch with a discovery node for finding the next 100+ prompt sources.
- **Tags:** `github-topics`, `discovery`, `prompt-corpus`, `index`
- **Safety / reproduction note:** Use as a map, not a quality filter; each repo needs separate review.
