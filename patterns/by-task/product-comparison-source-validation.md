# Candidate Pattern — Product Comparison Source Validation

Status: exploratory candidate; not runtime-promoted.

Evidence:

- Source candidates: PR106 and PR109
- Pilots: `2026-07-23-product-partial`, `2026-07-23-product-source-backed`
- Best observed use: current prices, exact SKUs, configuration-dependent measurements, warranty, availability, repairability, and total-cost comparisons

## Trigger

Apply when a recommendation depends on changing facts or when product family, SKU, configuration, market, test method, or sale condition can be mixed.

## Reusable move

```text
Before transferring a fact into the comparison, verify exact product identity, configuration, market, date, measurement method, and sale condition. Reject internally mismatched pages. Keep confirmed facts, conflicting evidence, inference, and unknowns separate. Block rankings that depend on unresolved identity, market, price, warranty, or configuration facts.
```

## Routing boundary

When the products or decision-critical configurations are missing, ask for the smallest missing set in one batch instead of generating a full research protocol.

## Do not apply

- stable explanations that do not require current facts
- casual comparisons where the user explicitly accepts rough category-level guidance
- requests with no named candidates, unless first used only to request missing information

## Main risks

- treating citations as proof of compatibility
- averaging conflicting prices into a plausible-looking range
- copying a family-level battery test into an exact SKU
- producing an empty answer when a useful partial comparison is still possible
