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
