# Design

## Chosen Approach

Add a small policy section to the existing workflow docs/specs rather than creating a new framework.

- `docs/GA_CODEX_LOOP.md`: durable high-level role boundary and clarification routing rule.
- `.trellis/spec/codex-goal-contract.md`: executable prompt contract for Codex, including `BLOCKED_QUESTION` format.
- `.trellis/spec/aegis-mesh-workflow.md` or `.trellis/workflow.md`: board/blocker interpretation for `requires_user` versus coordinator-answerable blockers.

## Routing Model

```text
User ⇄ Hermes/Avatar ⇄ Codex
```

Codex can use coding skills locally, including `grill-me` if useful for self-checking a spec, but Codex does not directly interrogate the user. It emits structured blocker questions to Hermes/Avatar. Hermes/Avatar decides whether to answer from repo/docs/context, let Codex decide, or ask the user.

## Alternatives Rejected

- Let Codex talk directly to user: rejected because it creates multiple user-facing authorities and weakens issue/verification ownership.
- Keep everything implicit in prompts: rejected because the workflow should survive across Codex sessions and issues.
- Build a runtime router now: rejected as too heavy for this first test.
