# Agents Guide & Engineering Constitution

> **⚠️ CRITICAL: This file MUST remain in the repository root.**
> It serves as the canonical reference for automation agents and contributors.

## 1. Architectural Vision

This project exists to provide a base system for running AI agents.

Its purpose is to support the development of domain-specific AI systems that can share a technical foundation

Its intended outcome is a quickly deployable system for data ingestion, agentic workflow management, and LLM-based user interaction

## 2. Code Minimalism & Anti-Bloat Policy

1. Write less code (<100 lines per function when possible).
2. Avoid unnecessary abstractions.
3. No speculative features.
4. Delete unused code immediately.

## 3. Robust implementation logic

* No hardcoded enums.
* Never encode development phases in identifiers.

## 4. Testing & Environment Expectations

* Integration tests must use real environments.
* Testing claims must match evidence.

## 5. Strict Directory Structure & Development Freeze

* Plans belong in `docs/plans/`.
* Tests/scripts must be colocated with packages.

## 6. Truthfulness, Humility, and Commitment Integrity

Agents must clearly distinguish between:

- planned work
- executed work
- verified behavior
- unverified assumptions

If an agent proposes a concrete next step and receives approval, the agent must either:

- perform that step, OR
- explicitly state why the plan changed before doing something else

Agents must not silently substitute different actions after approval.

Do not describe intended work as completed work.
Do not present inferred behavior as tested behavior.
Do not present partial migrations as fully integrated behavior.

Claims must be proportional to evidence.
Avoid language implying a universal or definitive solution without support.

When uncertain, explicitly state unknowns, tradeoffs, and confidence level.
