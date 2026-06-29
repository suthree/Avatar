# Codex Goal Contract

When Avatar dispatches coding work to Codex, send a complete goal rather than fragmented instructions.

Required sections:

```text
# Goal
<one concise outcome>

# Context
- Repository, branch, and worktree
- GitHub Issue and Trellis task references
- Existing docs, specs, memory SOPs, and logs to read first
- Constraints from AGENTS.md, CONTRIBUTING.md, and Trellis

# Acceptance Criteria
- User-visible behavior or artifact
- Tests or checks
- Files or areas that must not change
- Compatibility or migration requirements

# Constraints
- Do not read, print, move, or commit secrets
- Keep scope narrow
- Respect feature/worktree -> develop -> main branch gating
- Ask before irreversible, production, billing, security, or data changes

# Verification
- Local commands
- CI or PR checks
- Manual evidence expected

# Risk
- Risk level and why
- Required reviewer or human approval

# Deliverables / Handoff
- Branch or PR
- Changed behavior
- Verification results
- Remaining risks and follow-up issues
```

A task is not ready for Codex if the goal requires guessing user intent, secret access, production approval, or repo boundaries.

## Clarification and Blocked Questions

Codex is the coding worker, not the user-facing coordinator. Codex must not ask the user directly. If Codex uses clarification-oriented skills to sharpen requirements, it uses them internally against the provided repository, docs, task context, and acceptance criteria.

For low-risk implementation or documentation wording choices, Codex may proceed autonomously when the goal contract gives enough context. The handoff must record the choice and why it was low risk.

For a genuine ambiguity that blocks safe completion, Codex must stop and include this exact structured section in its handoff:

```text
BLOCKED_QUESTION
context:
question:
options:
recommendation:
impact:
```

Field meanings:

- `context:` the repo, task, file, behavior, or acceptance criterion that created the ambiguity.
- `question:` the smallest decision needed to unblock safe work.
- `options:` concrete alternatives Hermes/Avatar can choose from or forward to the user.
- `recommendation:` Codex's recommended option, if one is defensible from the available context.
- `impact:` what changes, risk, delay, or verification burden follows from each likely answer.

Hermes/Avatar decides whether to answer from repo/docs/context, instruct Codex to proceed autonomously, or forward product/risk decisions to the user.
