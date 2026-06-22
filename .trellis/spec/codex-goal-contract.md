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
