# Famous Prompts

## Purpose

Track notable prompts worth studying and adapting.

## Seed Entries (PR001–PR020)

### PR001
- **ID:** PR001
- **Name:** Awesome ChatGPT Prompts
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** prompt collection
- **Short excerpt:** Curated “Act as …” prompt patterns for many roles.
- **Structure summary:** Directory-style collection of role-based prompt starters with lightweight instructions and expected behavior framing.
- **Why it matters:** One of the most widely referenced early prompt libraries; influenced prompt-sharing conventions.
- **Tags:** `collection`, `role-prompt`, `chatgpt`, `foundational`
- **Safety / reproduction note:** Validate role prompts for misuse risk and update for current model policies before reuse.

### PR002
- **ID:** PR002
- **Name:** Act as Linux Terminal
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** role simulation / tool emulation
- **Short excerpt:** Requests the model to emulate shell I/O behavior.
- **Structure summary:** Defines strict output style (terminal-only responses), then iterates command-response turns.
- **Why it matters:** Canonical example of interface emulation via prompt constraints.
- **Tags:** `simulation`, `terminal`, `tool-emulation`, `format-control`
- **Safety / reproduction note:** Treat outputs as simulated text, not execution; never assume command results are real.

### PR003
- **ID:** PR003
- **Name:** Act as English Translator and Improver
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** translation / rewriting
- **Short excerpt:** Translate, correct, and improve user-provided wording.
- **Structure summary:** Assigns editor/translator role, sets quality target, and maps user input to revised output.
- **Why it matters:** Strong baseline for transformation prompts and style-preserving rewrites.
- **Tags:** `translation`, `editing`, `rewriting`, `language`
- **Safety / reproduction note:** Confirm factual meaning is preserved; avoid introducing unsupported claims during rewriting.

### PR004
- **ID:** PR004
- **Name:** Act as Interviewer
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** interview simulation
- **Short excerpt:** Conducts interviews one question at a time.
- **Structure summary:** Defines interviewer persona, sequencing rules, and turn-taking constraints.
- **Why it matters:** Useful pattern for multi-turn workflows and guided evaluation dialogs.
- **Tags:** `interview`, `multi-turn`, `persona`, `sequencing`
- **Safety / reproduction note:** Avoid collecting sensitive personal data in interview-style sessions.

### PR005
- **ID:** PR005
- **Name:** Act as JavaScript Console
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** tool simulation
- **Short excerpt:** Emulates JavaScript console outputs for code snippets.
- **Structure summary:** Locks response format to console-style output and suppresses extra explanation by default.
- **Why it matters:** Demonstrates strict response-shaping for developer utility prompts.
- **Tags:** `javascript`, `console`, `simulation`, `developer`
- **Safety / reproduction note:** Treat outputs as approximations; verify behavior in a real runtime.

### PR006
- **ID:** PR006
- **Name:** Act as Excel Sheet
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** interface simulation
- **Short excerpt:** Mimics spreadsheet-like interaction in plain text.
- **Structure summary:** Establishes grid/cell conventions and user-command patterns for pseudo-tabular operations.
- **Why it matters:** Early example of UI abstraction using natural language prompts.
- **Tags:** `spreadsheet`, `interface`, `simulation`, `tabular`
- **Safety / reproduction note:** Recheck calculations externally when correctness is critical.

### PR007
- **ID:** PR007
- **Name:** Act as Travel Guide
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** travel assistant
- **Short excerpt:** Suggests trip ideas using destination and preference context.
- **Structure summary:** Takes user constraints (budget, interests, time) and returns itinerary-style recommendations.
- **Why it matters:** Illustrates preference-conditioned recommendation prompts.
- **Tags:** `travel`, `recommendation`, `itinerary`, `assistant`
- **Safety / reproduction note:** Verify prices, visa rules, and local advisories from official current sources.

### PR008
- **ID:** PR008
- **Name:** Act as Plagiarism Checker
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** text evaluation
- **Short excerpt:** Evaluates text for potential similarity concerns.
- **Structure summary:** Frames model as reviewer scoring likely overlap and paraphrase risk based on provided content.
- **Why it matters:** Shows evaluative prompting for quality-control workflows.
- **Tags:** `evaluation`, `plagiarism`, `text-review`, `quality`
- **Safety / reproduction note:** Not a substitute for dedicated plagiarism detection systems or legal review.

### PR009
- **ID:** PR009
- **Name:** Act as Advertiser
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** marketing
- **Short excerpt:** Generates campaign concepts, slogans, and channel ideas.
- **Structure summary:** Accepts product + audience context, then returns positioning and creative options.
- **Why it matters:** Common pattern for structured ideation prompts in business contexts.
- **Tags:** `marketing`, `copywriting`, `campaign`, `ideation`
- **Safety / reproduction note:** Review outputs for compliance, truthfulness, and brand/legal constraints.

### PR010
- **ID:** PR010
- **Name:** Act as Storyteller
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** creative writing
- **Short excerpt:** Produces narrative content from user themes.
- **Structure summary:** Sets storytelling persona, tone cues, and plot-generation expectations.
- **Why it matters:** Foundational creative prompt archetype for tone and style control.
- **Tags:** `storytelling`, `creative`, `narrative`, `style`
- **Safety / reproduction note:** Screen outputs for harmful stereotypes and age-inappropriate content where relevant.

### PR011
- **ID:** PR011
- **Name:** Act as Prompt Enhancer
- **Source URL:** https://github.com/awesome-chatgpt-prompts/awesome-chatgpt-prompts-github
- **Platform:** GitHub
- **Type:** meta-prompt
- **Short excerpt:** Rewrites user prompts to improve clarity and specificity.
- **Structure summary:** Uses a transformation loop: analyze prompt intent, resolve ambiguity, output refined variant.
- **Why it matters:** Core meta-prompt pattern for prompt-optimization workflows.
- **Tags:** `meta-prompt`, `optimization`, `prompt-engineering`, `rewriting`
- **Safety / reproduction note:** Keep human review in the loop to avoid goal drift during enhancement.

### PR012
- **ID:** PR012
- **Name:** Awesome ChatGPT Prompts GitHub mirror
- **Source URL:** https://github.com/topics/awesome-chatgpt-prompts
- **Platform:** GitHub
- **Type:** prompt collection index
- **Short excerpt:** Topic page aggregating repositories for ChatGPT prompt collections.
- **Structure summary:** Discovery index organized by repository metadata rather than single prompt text.
- **Why it matters:** Useful for corpus expansion and source triangulation.
- **Tags:** `index`, `discovery`, `github-topics`, `collection`
- **Safety / reproduction note:** Vet repository quality, licensing, and recency before importing entries.

### PR013
- **ID:** PR013
- **Name:** yokoffing ChatGPT Prompts
- **Source URL:** https://github.com/yokoffing/ChatGPT-Prompts
- **Platform:** GitHub
- **Type:** prompt collection
- **Short excerpt:** Early curated prompt set spanning ChatGPT and Bing use cases.
- **Structure summary:** Mixed prompt catalog organized by task areas with concise usage framing.
- **Why it matters:** Historical snapshot of early mass-adopted prompting practices.
- **Tags:** `collection`, `historical`, `chatgpt`, `bing`
- **Safety / reproduction note:** Some patterns may be outdated; adapt for current model capabilities and policies.

### PR014
- **ID:** PR014
- **Name:** ai-boost awesome-prompts
- **Source URL:** https://github.com/ai-boost/awesome-prompts
- **Platform:** GitHub
- **Type:** prompt collection / GPT prompt scrape
- **Short excerpt:** Aggregated prompt lists including GPT Store-related materials.
- **Structure summary:** Broad scrape-style compilation with category grouping and mixed provenance.
- **Why it matters:** High-volume source for prompt mining and comparative analysis.
- **Tags:** `scrape`, `collection`, `gpt-store`, `aggregation`
- **Safety / reproduction note:** Confirm source provenance and copyright/licensing before redistribution.

### PR015
- **ID:** PR015
- **Name:** Top 100 GPTs Store Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/196y86v/top100_gpts_prompts_from_openai/
- **Platform:** Reddit
- **Type:** GPT Store prompt scrape
- **Short excerpt:** Community thread sharing scraped prompts from top GPT listings.
- **Structure summary:** Post-centric list with discussion context and community validation/challenges.
- **Why it matters:** Captures practitioner interest in real-world deployed GPT prompt patterns.
- **Tags:** `reddit`, `gpt-store`, `community`, `scrape`
- **Safety / reproduction note:** Treat as unverified community data; check terms and authenticity before reuse.

### PR016
- **ID:** PR016
- **Name:** 100000 AI Prompts
- **Source URL:** https://github.com/topics/chatgpt-prompts
- **Platform:** GitHub
- **Type:** large prompt dataset candidate
- **Short excerpt:** Large-scale prompt repositories discoverable via topic pages.
- **Structure summary:** Topic-driven discovery path for high-volume datasets and derivative collections.
- **Why it matters:** Supports dataset-scale experimentation and retrieval benchmarking.
- **Tags:** `dataset`, `large-scale`, `topics`, `corpus-building`
- **Safety / reproduction note:** Run deduplication, quality filtering, and policy screening before model training use.

### PR017
- **ID:** PR017
- **Name:** Awesome LLM Prompt Libraries
- **Source URL:** https://github.com/danielrosehill/awesome-llm-prompt-libraries
- **Platform:** GitHub
- **Type:** prompt library index
- **Short excerpt:** Curated index of LLM prompt-library resources.
- **Structure summary:** “Awesome list” format linking external collections by category.
- **Why it matters:** Good meta-source for discovering niche and domain prompt sets.
- **Tags:** `awesome-list`, `index`, `libraries`, `discovery`
- **Safety / reproduction note:** External links vary in quality; validate each source before adoption.

### PR018
- **ID:** PR018
- **Name:** gpt-prompt-pack
- **Source URL:** https://github.com/gethubai/gpt-prompt-pack
- **Platform:** GitHub
- **Type:** prompt pack
- **Short excerpt:** Role-oriented and utility prompts bundled for quick use.
- **Structure summary:** Packaged prompt modules with reusable templates and task groupings.
- **Why it matters:** Demonstrates portable prompt-pack pattern for operational reuse.
- **Tags:** `prompt-pack`, `templates`, `roles`, `utilities`
- **Safety / reproduction note:** Review for prompt-injection susceptibility in role instructions.

### PR019
- **ID:** PR019
- **Name:** ChatGPT Data Science Prompts
- **Source URL:** https://github.com/travistangvh/ChatGPT-Data-Science-Prompts
- **Platform:** GitHub
- **Type:** domain-specific prompt collection
- **Short excerpt:** Data science-oriented prompts for analysis, coding, and explanation tasks.
- **Structure summary:** Domain-focused prompt groups aligned to data workflows and analytics outputs.
- **Why it matters:** Useful benchmark for specialized prompting in technical domains.
- **Tags:** `data-science`, `domain-specific`, `analytics`, `technical`
- **Safety / reproduction note:** Validate statistical claims and code outputs independently.

### PR020
- **ID:** PR020
- **Name:** ChatGPT Prompts for Academic Writing
- **Source URL:** https://github.com/LeSinus/chatgpt-prompts-for-academic-writing
- **Platform:** GitHub
- **Type:** academic writing
- **Short excerpt:** Prompt examples for drafting and improving academic prose.
- **Structure summary:** Writing-stage templates (outline, drafting, polishing) targeted to scholarly contexts.
- **Why it matters:** Illustrates domain constraints like citation rigor and formal tone requirements.
- **Tags:** `academic-writing`, `education`, `editing`, `scholarly`
- **Safety / reproduction note:** Avoid fabricated citations; require source-backed claims and plagiarism checks.
