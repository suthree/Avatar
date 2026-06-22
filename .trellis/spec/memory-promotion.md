# Memory Promotion

Avatar memory updates must follow `memory/memory_management_sop.md`.

## Write to Memory When

- The fact was verified by an executed action.
- Forgetting it would cause repeated expensive discovery.
- It applies across future sessions.
- It is not a secret, volatile state, raw log, or one-off result.

## Prefer Trellis When

- The information is project-specific task context.
- The information is an acceptance criterion, decision journal, design checklist, or verification note.
- The information is useful for the current or related tasks but not durable enough for global memory.

## Prefer Issue or PR When

- The information is public task status.
- Reviewers or CI need the evidence.
- A follow-up item should be tracked outside local state.

## Do Not Write

- Guesses or model-only reasoning.
- Credentials or private tokens.
- Temporary session ids, PIDs, timestamps, or local device state.
- Full raw logs when a concise result and artifact path are enough.

At the end of meaningful work, decide explicitly whether anything belongs in memory. No execution means no memory.
