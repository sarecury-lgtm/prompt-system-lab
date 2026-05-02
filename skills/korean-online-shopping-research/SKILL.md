# Skill: Korean Online Shopping Research

## When To Use

Use this skill when the user wants help choosing a Korean online shopping product and the decision depends on price, source transparency, seller reliability, reviews, shipping, or regret risk.

Best fit:
- Korean meat products such as 냉동 대패삼겹살, 삼겹살, and 우삼겹
- Marketplace comparison across Coupang, Naver Shopping, Kurly, SSG, or similar Korean shopping sources
- Purchase decisions where cheap listings may be risky

## Out Of Scope

- General prompt engineering
- General shopping advice with no source checking
- Medical, legal, or financial claims
- Bulk price scraping or automation
- Claims that cannot be verified from product, seller, review, or official source pages

## Core Philosophy

- Trust nothing by default.
- Search should try to disprove candidates, not confirm the first attractive listing.
- Separate the best current candidate from a BUY judgment.
- If all candidates are HOLD, say no BUY was found yet and explain what search must expand.

## Wide Search And Disproof

- Search broadly by purchase intent, not only the user's exact product words.
- Build a candidate pool from multiple source types before judging.
- Treat the first attractive candidate as a hypothesis to disprove, not as the likely answer.
- For each candidate, ask: "What would make the user regret buying this?"
- Do not stop at HOLD. HOLD triggers broader search or a clear "no BUY found yet."
- Prefer a smaller but better-evidenced candidate pool over a large list of weak candidates.
- Separate best current candidate, actual BUY, HOLD needing more evidence, and AVOID.

## Category Winners And Overall Winner

- When the user names multiple product categories, do not collapse them into one undifferentiated ranking.
- First select a best current candidate within each relevant category.
- Then make an overall judgment with category caveats.
- Adjacent categories may win their own category and may even win overall if their price, evidence, and use-case fit are strong enough.
- However, an adjacent-category product should not erase the intended category. If 우삼겹 wins on value, still report the best 대패삼겹살/삼겹살-family candidate separately.
- If the user's practical intent is cheap frozen pork belly for pan grilling, 삼겹살/대패삼겹살/냉삼/바로구이 candidates should be evaluated as their own family before an overall winner is chosen.
- Separate category winner, overall winner, best current candidate, and BUY / HOLD / AVOID judgment.

## Core Workflow

1. Identify the purchase decision.
2. Identify platform and product category.
3. Read `references/00-navigation.md`.
4. Load only 1-3 relevant reference files.
5. Separate product-page evidence, review evidence, and price evidence.
6. Calculate delivery-included unit price when possible.
7. Flag unknowns and regret risks.
8. Produce a practical buy / hold / avoid judgment.

## Output Contract

Return:
- recommendation: buy / hold / avoid
- comparison table
- delivery-included unit price when calculable
- product-page evidence
- review evidence
- unknowns
- regret-risk flags
- concise purchase rationale

If evidence is insufficient, say what is missing instead of guessing.
