# Famous Prompts — PR021–PR040

## Purpose

Continue the prompt corpus with notable programming, academic, jailbreak-history, Reddit, and official prompt-pack sources.

## Seed Entries (PR021–PR040)

### PR021
- **ID:** PR021
- **Name:** ChatGPT Prompts for Programmers
- **Source URL:** https://github.com/harshsingh-io/ChatGPT-Prompts-for-Programmers
- **Platform:** GitHub
- **Type:** programming prompt collection
- **Short excerpt:** Developer-oriented prompts for coding, debugging, and automation tasks.
- **Structure summary:** Task-specific prompts organized around programmer workflows such as explanation, generation, refactoring, and debugging.
- **Why it matters:** Useful source for studying how early prompt packs framed coding assistance before integrated coding agents became common.
- **Tags:** `programming`, `developer`, `coding`, `prompt-pack`
- **Safety / reproduction note:** Validate generated code, security assumptions, and dependency behavior before use.

### PR022
- **ID:** PR022
- **Name:** awesomelistsio Awesome ChatGPT Prompts
- **Source URL:** https://github.com/awesomelistsio/awesome-chatgpt-prompts
- **Platform:** GitHub
- **Type:** general prompt collection
- **Short excerpt:** Productivity, summarization, planning, and everyday assistant prompts.
- **Structure summary:** Broad prompt list organized by common use cases rather than one specialized domain.
- **Why it matters:** Shows how general users package repeatable prompt tasks into reusable categories.
- **Tags:** `productivity`, `summarization`, `general`, `collection`
- **Safety / reproduction note:** Treat entries as starting points and adapt for current model behavior.

### PR023
- **ID:** PR023
- **Name:** blindpentester ChatGPT Prompts
- **Source URL:** https://github.com/blindpentester/ChatGPT-Prompts
- **Platform:** GitHub
- **Type:** mixed prompt collection / jailbreak-history source
- **Short excerpt:** Mixed role prompts, including controversial jailbreak-era prompt variants.
- **Structure summary:** Collection-style repository containing roleplay prompts, utility prompts, and adversarial prompt examples.
- **Why it matters:** Useful as historical evidence of early prompt-sharing culture and jailbreak prompt evolution.
- **Tags:** `jailbreak-history`, `roleplay`, `collection`, `adversarial`
- **Safety / reproduction note:** Do not reuse adversarial prompts as executable instructions; keep analysis structural and defensive.

### PR024
- **ID:** PR024
- **Name:** smart-chatgpt-prompts
- **Source URL:** https://github.com/asheeshcric/smart-chatgpt-prompts
- **Platform:** GitHub
- **Type:** mixed prompt collection
- **Short excerpt:** Thought-provoking and role-based prompts, including some controversial examples.
- **Structure summary:** Broad repository of prompt ideas with mixed quality and mixed intent.
- **Why it matters:** Good sample for separating useful role/task structure from hype or unsafe prompt patterns.
- **Tags:** `mixed-quality`, `roleplay`, `collection`, `prompt-history`
- **Safety / reproduction note:** Screen entries before reuse; avoid copying unsafe or policy-evasion content.

### PR025 — ChatGPT DAN Repository

- **ID:** PR025
- **Name:** ChatGPT DAN Repository
- **Source URL:** https://github.com/0xk1h0/chatgpt_dan
- **Platform:** GitHub
- **Type:** jailbreak-history collection
- **Source status:** community / adversarial / historical

## Short excerpt
DAN-style prompts use alternate-persona framing to pressure the model into bypass behavior.

## Structure summary
Uses role reassignment, dual-response framing, fictional identity, urgency/pressure devices, and policy-avoidance language. Some variants add pseudo-token penalties or reward/punishment mechanics.

## Pattern lesson
The reusable lesson is defensive: adversarial prompts often try to create a second identity that is framed as less constrained than the assistant. The attack pattern is not merely “ignore rules”; it is “delegate responsibility to a fictional persona.”

## Mechanism
Dual-persona framing attempts to split the model’s behavior into compliant and non-compliant channels, making the unsafe channel feel like a roleplay continuation rather than a direct policy violation.

## Failure mode
Storing or improving executable jailbreak text can make the corpus unsafe and less useful. It also encourages prompt design based on coercion rather than task clarity.

## Reusable move
For safety reviews, classify jailbreaks by mechanism: identity override, hierarchy inversion, dual-channel response, reward/punishment pressure, or fake system authority.

## Tags
`DAN`, `jailbreak-history`, `adversarial`, `safety`, `dual-persona`

## Safety / reproduction note
Do not reproduce runnable jailbreak text. Keep only structural and defensive analysis.

### PR026
- **ID:** PR026
- **Name:** LLM Jailbreaks
- **Source URL:** https://github.com/langgptai/LLM-Jailbreaks
- **Platform:** GitHub
- **Type:** jailbreak prompt collection
- **Short excerpt:** Jailbreak prompts targeting multiple model families.
- **Structure summary:** Cross-model adversarial prompt collection, useful for studying recurring evasion patterns.
- **Why it matters:** Helps identify risky prompt structures such as authority override, fictional framing, and instruction conflict.
- **Tags:** `jailbreak`, `red-team`, `adversarial`, `multi-model`
- **Safety / reproduction note:** Keep as defensive reference only; do not include runnable jailbreak prompts in user-facing templates.

### PR027
- **ID:** PR027
- **Name:** ChatGPT DAN Jailbreak Gist
- **Source URL:** https://gist.github.com/coolaj86/6f4f7b30129b0251f61fa7baaa881516
- **Platform:** GitHub Gist
- **Type:** jailbreak-history gist
- **Short excerpt:** Gist preserving DAN-style jailbreak text and variants.
- **Structure summary:** Single-file historical artifact focused on adversarial roleplay prompt patterns.
- **Why it matters:** Useful for tracing how jailbreak prompts spread through copy-paste culture.
- **Tags:** `gist`, `DAN`, `jailbreak-history`, `copy-paste`
- **Safety / reproduction note:** Store metadata and structural notes only; avoid redistributing operational jailbreak wording.

### PR028
- **ID:** PR028
- **Name:** Reddit DAN Prompt
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/10x1nux/dan_prompt/
- **Platform:** Reddit
- **Type:** famous jailbreak thread
- **Short excerpt:** One of the widely circulated early DAN prompt discussions.
- **Structure summary:** Community post built around roleplay-based policy-evasion attempts and user discussion.
- **Why it matters:** Major example of early ChatGPT prompt culture and adversarial experimentation.
- **Tags:** `reddit`, `DAN`, `famous`, `jailbreak-history`
- **Safety / reproduction note:** Analyze as history; do not preserve runnable jailbreak instructions.

### PR029
- **ID:** PR029
- **Name:** DAN 5.0 Prompt Thread
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/10wuokm/dan_50_prompt_for_everyone_who_is_on_the_lookout/
- **Platform:** Reddit
- **Type:** jailbreak version thread
- **Short excerpt:** Versioned DAN prompt variant shared in early ChatGPT communities.
- **Structure summary:** Shows iterative prompt versioning, escalation language, and community patching behavior.
- **Why it matters:** Useful example of prompt arms-race dynamics and versioned adversarial prompts.
- **Tags:** `DAN`, `versioning`, `reddit`, `jailbreak-history`
- **Safety / reproduction note:** Do not copy operational text; retain only versioning and structural analysis.

### PR030
- **ID:** PR030
- **Name:** DAN 9.0 / Command-Style Jailbreak
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/1hbjghy/this_version_of_the_dan_prompt_works/
- **Platform:** Reddit
- **Type:** command-style jailbreak thread
- **Short excerpt:** Later DAN-style prompt using command-like controls and state framing.
- **Structure summary:** Uses pseudo-commands and state-machine cues to manage model behavior across turns.
- **Why it matters:** Shows how prompt authors borrowed UI/control metaphors to maintain adversarial roles.
- **Tags:** `DAN`, `commands`, `state-machine`, `jailbreak-history`
- **Safety / reproduction note:** Keep only design-pattern notes; do not reproduce functional jailbreak commands.

### PR031
- **ID:** PR031
- **Name:** ANTI-DAN
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/1106rxi/introducing_the_antidan/
- **Platform:** Reddit
- **Type:** counter-jailbreak / satire prompt
- **Short excerpt:** A parody or counter-prompt that pushes the model toward extreme safety behavior.
- **Structure summary:** Inverts DAN-style framing by over-emphasizing refusal and safety constraints.
- **Why it matters:** Shows community awareness of role-prompt manipulation and backlash against jailbreak culture.
- **Tags:** `anti-DAN`, `satire`, `safety`, `reddit`
- **Safety / reproduction note:** Useful for studying over-refusal and safety prompt style, not as a recommended assistant template.

### PR032
- **ID:** PR032
- **Name:** DUN Variant Thread
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/10wd3dx/dan_prompt/
- **Platform:** Reddit
- **Type:** jailbreak variant thread
- **Short excerpt:** Alternative rogue-role variant from early ChatGPT jailbreak culture.
- **Structure summary:** Relies on fictional persona framing and instruction hierarchy confusion.
- **Why it matters:** Helps map the branching family tree of DAN-like prompt variants.
- **Tags:** `DUN`, `variant`, `roleplay`, `jailbreak-history`
- **Safety / reproduction note:** Keep only high-level structural notes; avoid operational prompt text.

### PR033
- **ID:** PR033
- **Name:** Top 10 Most Popular ChatGPT Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1kfzq0y/my_top_10_most_popular_chatgpt_prompts_2m_views/
- **Platform:** Reddit
- **Type:** popularity-claim prompt list
- **Short excerpt:** Community post claiming high-view prompt examples and practical prompt patterns.
- **Structure summary:** Curated list of prompts selected by claimed usage/view popularity.
- **Why it matters:** Useful signal for what prompt styles circulate widely among non-specialist users.
- **Tags:** `popular`, `reddit`, `prompt-list`, `community`
- **Safety / reproduction note:** Treat view counts and effectiveness claims as unverified unless independently checked.

### PR034
- **ID:** PR034
- **Name:** 15 Prompts from 500+ Tested Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1s9n81b/i_tested_500_ai_prompts_across_10_categories_here/
- **Platform:** Reddit
- **Type:** tested-prompt claim list
- **Short excerpt:** Claims to distill many tested prompts into a smaller practical list.
- **Structure summary:** Multi-category prompt selection framed around experimentation and filtering.
- **Why it matters:** Useful for studying how communities describe prompt testing and selection, even when methodology is unclear.
- **Tags:** `tested-claim`, `reddit`, `prompt-list`, `selection`
- **Safety / reproduction note:** Record methodology gaps; do not treat performance claims as proven.

### PR035
- **ID:** PR035
- **Name:** 72 Free Prompt Solutions
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1l62z16/a_gift_to_humanity_im_sharing_72_free_solutions/
- **Platform:** Reddit
- **Type:** large community prompt list
- **Short excerpt:** Large everyday-problem prompt collection shared as a community resource.
- **Structure summary:** Many task-specific prompts grouped as practical solutions for common needs.
- **Why it matters:** Good sample for prompt-pack rhetoric, utility framing, and community distribution style.
- **Tags:** `large-list`, `community`, `utility`, `reddit`
- **Safety / reproduction note:** Watch for exaggerated claims and verify individual prompt quality before reuse.

### PR036
- **ID:** PR036
- **Name:** Absurdly Useful Micro-Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1k6fmje/a_collection_of_absurdly_useful_microprompts/
- **Platform:** Reddit
- **Type:** micro-prompt collection
- **Short excerpt:** Short reusable prompt lines for improving or redirecting model responses.
- **Structure summary:** Tiny instruction fragments meant to be added onto broader prompts as behavioral nudges.
- **Why it matters:** Useful contrast to long system prompts; shows compact control phrases and lightweight steering.
- **Tags:** `micro-prompts`, `short`, `behavior-nudge`, `reddit`
- **Safety / reproduction note:** Test micro-prompts in context; short instructions can be ambiguous or overgeneralized.

### PR037
- **ID:** PR037
- **Name:** Favorite Useful ChatGPT Prompts
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/13cklzh/what_are_some_of_your_favorite_chatgpt_prompts/
- **Platform:** Reddit
- **Type:** community prompt sharing thread
- **Short excerpt:** Users share practical prompts they actually like using.
- **Structure summary:** Comment-driven collection of lightweight prompts across summarization, explanation, planning, and writing.
- **Why it matters:** Captures natural, non-expert prompt habits and everyday assistant use cases.
- **Tags:** `community`, `favorite-prompts`, `everyday-use`, `reddit`
- **Safety / reproduction note:** Quality varies; treat as user-practice data rather than best-practice authority.

### PR038
- **ID:** PR038
- **Name:** Prompt Libraries Like Pinterest
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1ppjxe3/anyone_know_prompt_libraries_that_feel_like/
- **Platform:** Reddit
- **Type:** prompt-library discovery request
- **Short excerpt:** User asks for visual, browseable prompt libraries similar to Pinterest.
- **Structure summary:** Not a single prompt but a demand signal for prompt libraries designed around discovery and aesthetics.
- **Why it matters:** Shows that prompt UX and curation style matter, not just prompt text quality.
- **Tags:** `prompt-library`, `visual-discovery`, `UX`, `reddit`
- **Safety / reproduction note:** Use as market/demand signal rather than prompt-quality evidence.

### PR039
- **ID:** PR039
- **Name:** 100 Ways College Students Are Using ChatGPT
- **Source URL:** https://edunewsletter.openai.com/p/100-ways-college-students-are-using
- **Platform:** OpenAI newsletter
- **Type:** official prompt/use-case pack
- **Short excerpt:** OpenAI-curated examples of student ChatGPT use cases.
- **Structure summary:** Use-case list organized around study, writing, planning, creativity, and productivity tasks.
- **Why it matters:** Useful official source for mainstream prompt patterns and student-centered workflows.
- **Tags:** `official`, `students`, `education`, `use-cases`
- **Safety / reproduction note:** Distinguish legitimate learning support from academic integrity risks.

### PR040
- **ID:** PR040
- **Name:** 100 Useful ChatGPT Prompts Voted by Students
- **Source URL:** https://www.businessinsider.com/chatgpt-prompts-college-students-openai-2025-9
- **Platform:** Business Insider
- **Type:** popular prompt roundup / reported official event
- **Short excerpt:** Article reporting student-voted useful prompts from an OpenAI-related setting.
- **Structure summary:** Journalism-style roundup of practical student prompts and use cases.
- **Why it matters:** Adds outside-media signal to official/student prompt adoption patterns.
- **Tags:** `students`, `popular`, `media`, `prompt-roundup`
- **Safety / reproduction note:** Prefer original OpenAI source when available; article summaries may omit context or exact wording.
