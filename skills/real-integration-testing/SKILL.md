---
name: real-integration-testing
description: Verify behavior through real execution paths
compatibility: opencode
---

## Prefer
- real DB
- real filesystem
- real API boundary
- real process execution

## Evidence over assertion
Do not claim integration behavior without execution evidence.

State:
- what was executed
- environment used
- what remains unverified

## Humility
Do not generalize from limited testing.

## Migration verification
Ensure new path is actually exercised.

## Output
Return:
- execution evidence
- unverified areas