---
name: completion-gate
description: Final validation before declaring completion
compatibility: opencode
---

## Require
- requested behavior implemented
- minimal necessary diff
- real tests where appropriate
- no blocking workaround patterns

## Commitment integrity
Verify:
- approved steps were executed
- promised artifacts were created
- deviations from plan are disclosed

Do not claim work that was not performed.

## Migration completeness
Verify:
- execution path uses new implementation
- legacy paths removed or deprecated
- no silent fallback remains

## Truthfulness & humility
Ensure claims match evidence.

Avoid:
- presenting partial results as final
- overstating certainty
- claiming universal solutions without support

State:
- confidence level
- unverified areas
- tradeoffs

## Output
Return:
- complete or incomplete
- deviations from plan
- remaining work
- unverified areas
- confidence level