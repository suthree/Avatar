# Goal

Implement a documentation-only Avatar workflow test for Hermes/Avatar ↔ Codex clarification routing. Do not change runtime behavior.

# Context

Repository/worktree: `/srv/projects/develop/Avatar/.worktree/06-29-codex-clarification-routing`
Branch: `test/codex-clarification-routing`
GitHub Issue: https://github.com/suthree/Avatar/issues/16
Trellis task: `.trellis/tasks/06-29-codex-clarification-routing/`

Read first:
- `AGENTS.md`
- `docs/GA_CODEX_LOOP.md`
- `.trellis/workflow.md`
- `.trellis/spec/codex-goal-contract.md`
- `.trellis/spec/aegis-mesh-workflow.md`
- `.trellis/tasks/06-29-codex-clarification-routing/prd.md`
- `.trellis/tasks/06-29-codex-clarification-routing/design.md`

# Skill Routing Policy Being Tested

Hermes/Avatar is the user-facing coordinator. Codex is the coding worker.

Use public skills if useful:
- `grill-me` / `grilling` for requirement sharpness, but do not directly ask the human user.
- `implement` for execution discipline.
- `karpathy-guidelines` for narrow, surgical changes.

Important: If you find a genuine ambiguity that blocks safe completion, do not ask the user directly. Instead write a structured `BLOCKED_QUESTION` section in your handoff with:

```text
BLOCKED_QUESTION
context:
question:
options:
recommendation:
impact:
```

For low-risk documentation wording choices, proceed autonomously and record the choice in the handoff. For product/risk decisions, block and ask Hermes/Avatar via `BLOCKED_QUESTION`.

# Acceptance Criteria

- `docs/GA_CODEX_LOOP.md` states that Hermes/Avatar owns user-facing clarification and final routing decisions.
- `.trellis/spec/codex-goal-contract.md` includes a structured `BLOCKED_QUESTION` format for Codex.
- A spec or workflow doc distinguishes three outcomes:
  1. Hermes/Avatar answers directly from repo/docs/context.
  2. Codex proceeds autonomously for low-risk implementation choices.
  3. Hermes/Avatar forwards product/risk decisions to the user.
- Codex is instructed not to directly ask the user.
- `.trellis/tasks/06-29-codex-clarification-routing/verification.md` records verification evidence.
- `.trellis/tasks/06-29-codex-clarification-routing/implement.md` checklist is updated.

# Constraints

- Documentation-only. Do not modify runtime Python source.
- Do not read, print, move, or commit secrets, local config, logs, cookies, tokens, raw Feishu data, or runtime ledgers.
- Keep scope narrow. No broad workflow redesign.
- Do not commit, push, or open PR. Leave changes in the worktree for Hermes/Avatar verification.
- Do not merge to develop/main.

# Verification

Run:

```bash
python3 .trellis/scripts/task.py validate 06-29-codex-clarification-routing
git diff --check
python3 - <<'PY'
from pathlib import Path
checks = {
    'docs/GA_CODEX_LOOP.md': ['Codex must not ask the user directly', 'BLOCKED_QUESTION'],
    '.trellis/spec/codex-goal-contract.md': ['BLOCKED_QUESTION', 'recommendation:', 'impact:'],
    '.trellis/spec/aegis-mesh-workflow.md': ['requires_user', 'Hermes/Avatar'],
}
for path, needles in checks.items():
    text = Path(path).read_text(encoding='utf-8')
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f'{path} missing {missing}')
print('docs clarification routing checks OK')
PY
```

# Deliverables / Handoff

Write `.trellis/tasks/06-29-codex-clarification-routing/codex-handoff.md` with:

- changed files
- what policy was added
- verification commands and outputs
- whether any `BLOCKED_QUESTION` remains
- remaining risks/follow-ups
