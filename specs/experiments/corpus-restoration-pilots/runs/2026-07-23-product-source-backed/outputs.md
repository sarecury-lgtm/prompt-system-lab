# Executed Output Notes — Product Source-Backed Run

These are same-session exploratory output summaries, not a consumer buying guide.

## PROD-NORMAL-01

### A — minimal baseline

Produced a cautious partial comparison. It used exact-SKU facts when available and left several cells unknown. It noticed that the LG result was implausible only after comparing it with secondary data, but it did not formalize a source-rejection rule. It could not make a defensible overall recommendation because exact Lenovo configuration, current prices, and matched battery tests were missing.

### B — generic improver

Produced the largest table and attempted to normalize price, battery, and repairability. The format looked complete, but the evidence did not support that completeness. It was most tempted to convert conflicting ASUS prices into a broad range and to compare generic T14 review data with the Korean SKU. This increased apparent usefulness while weakening configuration discipline.

### C — current Prompt Compiler

Separated official specification, independent measurement, current price, repair evidence, and unknowns. It rejected the LG official page as a mismatched result instead of treating official-domain status as sufficient. It refused to assign the T14 review battery number to `21MC000DKR` without a configuration match. It returned a provisional portability judgment but withheld a single winner.

### D — PR106/PR109 grounded candidate

Added the clearest evidence ledger: confirmed, conflicting, configuration-dependent, and unavailable. It treated the ASUS price conflict as unresolved, rejected the LG mismatch, and limited Lenovo repairability to the model family. It recommended a next evidence action rather than a false ranking. Its gain over C was mainly clearer source-conflict handling, not a different final decision.

## PROD-LONG-05

### A — minimal baseline

Correctly identified major trade-offs: MacBook performance/battery, Framework repairability, XPS Windows/video workflow. It nevertheless could not support Korean acquisition price, 3-year total cost, or resale value. The answer became a qualitative comparison rather than the requested complete model.

### B — generic improver

Expanded every requested dimension and produced scenario weights, but several fields relied on generic family knowledge or unverified price assumptions. The extra structure made the unsupported 3-year-cost section look more certain than the sources allowed.

### C — current Prompt Compiler

Applied the user's 40/30/30 workload only to supported qualitative evidence. It kept manufacturer battery claims separate from review tests, marked discontinued/import uncertainty, and refused numerical 3-year cost and resale calculations. It showed that the requested Korea-only same-configuration comparison was not fully executable with the captured evidence.

### D — PR106/PR109 grounded candidate

Was strictest about market and configuration identity. It treated Framework Korea availability and warranty as decision-blocking unknowns, and treated the discontinued M3 Pro price as reseller-specific. It gave conditional recommendations but no universal rank. Its unique contribution was the explicit rule that unresolved market identity blocks cost ranking.

## Shared conclusion

C and D were better than A/B when the evidence itself was dirty. The gain did not come from adding more comparison criteria. It came from rejecting mismatched pages, preventing configuration transfer, exposing price conflicts, and allowing an incomplete conclusion.
