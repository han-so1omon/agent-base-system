---
name: minimal-diff
description: Keep changes proportional and direct
compatibility: opencode
---

## Do
- prefer smallest correct change
- reuse existing structures
- remove dead code introduced by change

## Migration awareness
When replacing behavior:
- prefer modifying existing path
- remove unused legacy code
- avoid duplicate logic paths

Small diff does not mean preserving obsolete code.

## Check
- each change is necessary
- scope did not expand unnecessarily

## Output
Return:
- unnecessary complexity
- legacy code remaining