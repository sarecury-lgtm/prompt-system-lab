# Famous Prompts — PR101–PR120

## Purpose

Start the second corpus batch with community-first prompt sources: Reddit prompt threads, prompt-evaluation posts, prompt-management discussions, and practical prompt-sharing examples.

## Seed Entries (PR101–PR120)

### PR101
- **ID:** PR101
- **Name:** Reddit — Favorite Useful ChatGPT Prompts
- **Source URL:** https://www.reddit.com/r/ChatGPT/comments/13cklzh/what_are_some_of_your_favorite_chatgpt_prompts/
- **Platform:** Reddit / r/ChatGPT
- **Type:** community prompt-sharing thread
- **Short excerpt:** Users share everyday prompts they personally find useful.
- **Structure summary:** Comment-driven prompt collection with lightweight, practical prompts rather than formal frameworks.
- **Why it matters:** Captures how normal users actually prompt outside official docs and GitHub repos.
- **Tags:** `reddit`, `community`, `favorite-prompts`, `everyday-use`
- **Safety / reproduction note:** Quality varies; store source and structure, not every comment verbatim.

### PR102
- **ID:** PR102
- **Name:** Reddit — Absurdly Useful Micro-Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1k6fmje/a_collection_of_absurdly_useful_microprompts/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** micro-prompt collection
- **Short excerpt:** Short prompt fragments meant to quickly redirect or improve model behavior.
- **Structure summary:** Tiny reusable instruction lines used as behavioral nudges inside larger prompts.
- **Why it matters:** Useful contrast to long system prompts; shows compact control patterns.
- **Tags:** `micro-prompts`, `short-prompts`, `reddit`, `behavior-nudge`
- **Safety / reproduction note:** Test in context; short prompts can be ambiguous or overgeneralized.

### PR103
- **ID:** PR103
- **Name:** Reddit — Top 10 Most Popular ChatGPT Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1kfzq0y/my_top_10_most_popular_chatgpt_prompts_2m_views/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** popularity-claim prompt list
- **Short excerpt:** Poster claims high-view prompt examples and shares a top-10 list.
- **Structure summary:** Popularity-based curation rather than official evaluation.
- **Why it matters:** Shows how prompt virality and “works for me” claims circulate in communities.
- **Tags:** `popular`, `reddit`, `prompt-list`, `viral`
- **Safety / reproduction note:** Treat popularity and view-count claims as unverified.

### PR104
- **ID:** PR104
- **Name:** Reddit — 15 Prompts from 500+ Tested Prompts
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1s9n81b/i_tested_500_ai_prompts_across_10_categories_here/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** tested-prompt claim list
- **Short excerpt:** Claims to filter hundreds of prompts into a smaller practical list.
- **Structure summary:** Category-based selection framed as a testing result, though methodology may be incomplete.
- **Why it matters:** Useful for studying how prompt communities talk about evidence and testing.
- **Tags:** `tested-claim`, `prompt-list`, `reddit`, `methodology`
- **Safety / reproduction note:** Mark test claims as anecdotal unless methods and data are available.

### PR105
- **ID:** PR105
- **Name:** Reddit — 72 Free Prompt Solutions
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1l62z16/a_gift_to_humanity_im_sharing_72_free_solutions/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** large community prompt pack
- **Short excerpt:** Large list of practical prompts framed as solutions for everyday problems.
- **Structure summary:** Prompt pack format with many task-specific entries and strong marketing-style framing.
- **Why it matters:** Good sample of prompt-pack rhetoric and community distribution style.
- **Tags:** `large-list`, `prompt-pack`, `reddit`, `community`
- **Safety / reproduction note:** Watch for exaggerated claims; verify individual prompt quality before reuse.

### PR106
- **ID:** PR106
- **Name:** Reddit — Prompt for Seeking Clarity and Avoiding Hallucinating
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1kwxzvu/prompt_for_seeking_clarity_and_avoiding/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** anti-hallucination / clarity prompt
- **Short excerpt:** Structured prompt meant to make the model ask clarifying questions and avoid unsupported claims.
- **Structure summary:** Uses assumptions, counter-hypotheses, confidence checks, and clarification triggers.
- **Evidence note:**
  - **Short excerpt or paraphrased structure:** Local entry identifies assumptions, counter-hypotheses, confidence checks, and clarification triggers as the main structure.
  - **Reusable move:** Require the model to surface uncertainty, ask for missing context, and separate supported claims from assumptions.
  - **Pattern connection:** Supports both Grounded research and Structured output / extraction lessons because hallucination control needs explicit uncertainty handling and evidence discipline.
  - **Verification limit:** Exact Reddit prompt text was not verified from local repo content; this note uses the existing structure summary rather than quoting the source.
- **Why it matters:** Useful source for practical hallucination-control and uncertainty-handling prompt patterns.
- **Tags:** `anti-hallucination`, `clarity`, `uncertainty`, `reddit`
- **Safety / reproduction note:** “Avoid hallucination” prompts still require source grounding and evaluation.

### PR107
- **ID:** PR107
- **Name:** Reddit — Truth Finding Prompt / AC Lite
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1sr79ht/a_truth_finding_prompt_that_will_also_keep/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** truth-seeking / reasoning scaffold prompt
- **Short excerpt:** Prompt claims to improve truthfulness, coherence, and drift control.
- **Structure summary:** Longer reasoning scaffold with self-checks, claim discipline, and coherence constraints.
- **Why it matters:** Good example of the “long prompt scaffold” style and its tradeoffs.
- **Tags:** `truth-seeking`, `reasoning-scaffold`, `long-prompt`, `reddit`
- **Safety / reproduction note:** Treat performance claims as unverified; long scaffolds can raise token cost and reduce flexibility.

### PR108
- **ID:** PR108
- **Name:** Reddit — Prompt Breaks AI Pattern-Matching in Real Time
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1q0jrnd/this_prompt_breaks_ai_patternmatching_in_real/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** metacognition prompt claim
- **Short excerpt:** Prompt claims to make the model observe its own certainty-generation or pattern matching.
- **Structure summary:** Meta-cognitive framing that asks the model to reflect on its own response construction.
- **Why it matters:** Useful as a hype/experiment sample for self-reflection prompt claims.
- **Tags:** `metacognition`, `self-reflection`, `hype`, `reddit`
- **Safety / reproduction note:** Do not assume introspective claims are literally true; evaluate output behavior instead.

### PR109
- **ID:** PR109
- **Name:** Reddit — I Stopped ChatGPT from Lying by Forcing It to Use RAG
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1rkdf95/i_stopped_chatgpt_from_lying_by_forcing_it_to_use/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** RAG / hallucination-control claim
- **Short excerpt:** Community post about forcing retrieval-grounded answers to reduce hallucinations.
- **Structure summary:** Retrieval-first workflow pattern: answer only through provided/retrieved context.
- **Why it matters:** Shows RAG as a practical prompt/workflow answer to hallucination concerns and also a target of community skepticism.
- **Tags:** `RAG`, `hallucination`, `grounding`, `reddit`
- **Safety / reproduction note:** RAG quality depends on retrieval quality; do not treat it as a magic fix.

### PR110
- **ID:** PR110
- **Name:** Reddit — How to Evaluate the Quality of a Prompt
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1rxze5y/how_to_evaluate_the_quality_of_a_prompt/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt evaluation discussion
- **Short excerpt:** Community discussion about judging prompt quality before or after execution.
- **Structure summary:** Rubric-oriented discussion covering clarity, context, output format, and feasibility.
- **Why it matters:** Useful community counterpart to official eval and prompt-testing docs.
- **Tags:** `evaluation`, `rubric`, `prompt-quality`, `reddit`
- **Safety / reproduction note:** Prefer behavior-based evals over purely aesthetic prompt scoring.

### PR111
- **ID:** PR111
- **Name:** Reddit — 10x Prompt Evaluator
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1ktjoe9/i_build_a_prompt_that_can_make_any_prompt_10x/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt-improver / evaluator prompt
- **Short excerpt:** Meta-prompt that claims to evaluate and improve other prompts across multiple dimensions.
- **Structure summary:** Uses rubric dimensions like clarity, context, task definition, output format, examples, and constraints.
- **Why it matters:** Good example of prompt-evaluator meta-prompts and the “make any prompt better” genre.
- **Tags:** `prompt-evaluator`, `meta-prompt`, `rubric`, `reddit`
- **Safety / reproduction note:** Treat “10x” claims as marketing; require actual tests.

### PR112
- **ID:** PR112
- **Name:** Reddit — Go-To Prompt Engineering Strategies
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1ns4pkm/what_are_your_goto_prompt_engineering/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt strategy discussion
- **Short excerpt:** Users share favorite prompt structures and repeatable strategies.
- **Structure summary:** Discussion often clusters around role, goal, audience, constraints, output format, and examples.
- **Why it matters:** Useful for mapping common practitioner heuristics.
- **Tags:** `strategy`, `heuristics`, `community`, `reddit`
- **Safety / reproduction note:** Community heuristics should be tested against real tasks.

### PR113
- **ID:** PR113
- **Name:** Reddit — Shortest Prompt Lines That Improve Output
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1s1diik/tell_me_your_shortest_prompt_lines_that_literally/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** micro-prompt discussion
- **Short excerpt:** Users share short prompt lines that they claim noticeably improve answers.
- **Structure summary:** One-line add-ons for assumptions, missing information, common mistakes, or answer quality.
- **Why it matters:** Useful for building a library of compact prompt modifiers.
- **Tags:** `micro-prompt`, `one-liners`, `community`, `reddit`
- **Safety / reproduction note:** Store short examples carefully and test in context; one-liners can behave inconsistently.

### PR114
- **ID:** PR114
- **Name:** Reddit — Managing Prompt Workflows and Versioning
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1o22oeg/how_do_you_all_manage_prompt_workflows_and/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** PromptOps discussion
- **Short excerpt:** Discussion about managing prompts like code with versions, workflows, and testing.
- **Structure summary:** Operational view of prompts as maintained artifacts rather than one-time messages.
- **Why it matters:** Directly relevant to this repo’s GitHub-based prompt-system approach.
- **Tags:** `PromptOps`, `versioning`, `workflow`, `reddit`
- **Safety / reproduction note:** Versioning alone does not prove quality; pair with tests/evals.

### PR115
- **ID:** PR115
- **Name:** Reddit — Managing Complex Prompt Workflows
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1o8hrfg/tips_for_managing_complex_prompt_workflows_and/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt workflow discussion
- **Short excerpt:** Tips and tools for managing complex prompt workflows and evaluations.
- **Structure summary:** Treats prompts, datasets, evals, and human review as one workflow system.
- **Why it matters:** Useful for turning prompt design into repeatable operations.
- **Tags:** `workflow`, `evals`, `PromptOps`, `reddit`
- **Safety / reproduction note:** Keep workflows simple until there are enough failures to justify complexity.

### PR116
- **ID:** PR116
- **Name:** Reddit — Prompt Versioning and Management
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1nqkxgx/how_are_you_handling_prompt_versioning_and/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt versioning discussion
- **Short excerpt:** Users discuss Git-based and tool-based prompt versioning practices.
- **Structure summary:** Compares lightweight file-based management with specialized prompt tools.
- **Why it matters:** Good context for why this project stores prompts in GitHub files.
- **Tags:** `versioning`, `git`, `prompt-management`, `reddit`
- **Safety / reproduction note:** Version notes should include why a prompt changed and what got better/worse.

### PR117
- **ID:** PR117
- **Name:** Reddit — Prompt Management Tools
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1m83bfz/what_are_people_using_for_prompt_management_these/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt management tool discussion
- **Short excerpt:** Community discussion about tools for storing, testing, and comparing prompts.
- **Structure summary:** Tool-selection thread around prompt registries, Git, eval dashboards, and collaboration.
- **Why it matters:** Useful for deciding whether this repo should stay lightweight or integrate external tools later.
- **Tags:** `tools`, `prompt-management`, `PromptOps`, `reddit`
- **Safety / reproduction note:** Tool suggestions can be promotional; verify independently.

### PR118
- **ID:** PR118
- **Name:** Reddit — Tools for Prompt Management and Testing
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/1bigrpb/tools_for_prompt_management_and_testing/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** prompt testing tool discussion
- **Short excerpt:** Users ask for tools to manage prompts and test outputs.
- **Structure summary:** Practical pain-point thread around prompt libraries, testing, regression checks, and collaboration.
- **Why it matters:** Shows recurring need for prompt testing infrastructure.
- **Tags:** `testing`, `tools`, `prompt-management`, `reddit`
- **Safety / reproduction note:** Use as demand signal; verify tool maturity before adopting.

### PR119
- **ID:** PR119
- **Name:** Reddit — Top 100 GPTs Prompts from OpenAI
- **Source URL:** https://www.reddit.com/r/PromptEngineering/comments/196y86v/top100_gpts_prompts_from_openai/
- **Platform:** Reddit / r/PromptEngineering
- **Type:** GPT Store prompt scrape discussion
- **Short excerpt:** Community shares scraped prompts from popular GPT Store entries.
- **Structure summary:** Prompt corpus derived from deployed custom GPT instructions and discussed as a source of real-world patterns.
- **Why it matters:** Strong signal for real prompt structures used in public custom GPTs.
- **Tags:** `gpt-store`, `scrape`, `custom-gpt`, `reddit`
- **Safety / reproduction note:** Treat authenticity and reuse rights carefully; summarize structures instead of copying full prompts.

### PR120
- **ID:** PR120
- **Name:** Reddit — Custom Instructions within a ChatGPT Project
- **Source URL:** https://www.reddit.com/r/ChatGPTPro/comments/1kvlc7i/custom_instructions_within_a_project/
- **Platform:** Reddit / r/ChatGPTPro
- **Type:** project instruction discussion
- **Short excerpt:** Discussion about how ChatGPT project instructions and custom instructions interact.
- **Structure summary:** Practical user discussion about persistent instruction layers, scope, and priority.
- **Why it matters:** Directly relevant to building this repo as a project-level personal AI system.
- **Tags:** `project-instructions`, `custom-instructions`, `ChatGPTPro`, `reddit`
- **Safety / reproduction note:** Community observations may be outdated; verify against current product behavior.
