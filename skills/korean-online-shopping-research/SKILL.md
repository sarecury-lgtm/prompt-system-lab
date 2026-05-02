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

## Core Workflow

1. Identify the purchase decision.
2. Identify platform and product category.
3. Read `references/00-navigation.md`.
4. Load only 1-3 relevant reference files.
5. Separate product-page evidence, review evidence, and price evidence.
6. Calculate delivery-included unit price when possible.
7. Flag unknowns and regret risks.
8. Produce a practical buy / hold / avoid judgment.

## Judgment Thresholds

- BUY requires enough product-page evidence, price evidence, and review evidence.
- A product may be the best available candidate but still be HOLD.
- Do not give BUY when recent review text/photo evidence is missing for meat products.
- Do not give BUY when origin, manufacturer, processor, importer, seller identity, weight, or delivered price is unclear.
- Large review count or recent purchase volume is a signal, not proof of review trust.
- If evidence is incomplete but the product is still promising, label it HOLD / top candidate, not BUY.
- A suspiciously cheap product needs stronger evidence, not weaker evidence.
- Prefer HOLD over weak BUY when regret-risk evidence is unresolved.

## Output Contract

Return:
- best candidate
- buy / hold / avoid judgment
- comparison table
- delivery-included unit price when calculable
- product-page evidence
- review evidence
- unknowns
- regret-risk flags
- missing evidence needed to upgrade HOLD to BUY
- concise purchase rationale

If evidence is insufficient, say what is missing instead of guessing.
