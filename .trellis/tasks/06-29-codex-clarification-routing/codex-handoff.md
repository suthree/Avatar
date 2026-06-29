# Codex Handoff

## Changed Files

- `docs/GA_CODEX_LOOP.md`
- `.trellis/spec/codex-goal-contract.md`
- `.trellis/spec/aegis-mesh-workflow.md`
- `.trellis/tasks/06-29-codex-clarification-routing/implement.md`
- `.trellis/tasks/06-29-codex-clarification-routing/verification.md`
- `.trellis/tasks/06-29-codex-clarification-routing/codex-handoff.md`

## Policy Added

- Hermes/Avatar owns user-facing clarification and final routing decisions.
- Codex must not ask the user directly.
- Codex may proceed autonomously for low-risk implementation or documentation wording choices when the goal context is sufficient, and must record the choice in the handoff.
- Codex must emit a structured `BLOCKED_QUESTION` when a genuine ambiguity blocks safe completion.
- Hermes/Avatar routes blocked questions into three outcomes:
  1. answer directly from repo/docs/task context or verified memory;
  2. confirm Codex may proceed autonomously for a low-risk implementation choice;
  3. forward product, risk, approval, or user-preference decisions to the user.

Low-risk wording choice recorded: the Aegis Mesh outcomes use `avatar_answered`, `codex_autonomous`, and `requires_user` labels to make the three routing states easy to scan without adding runtime behavior.

## Verification

```bash
python3 .trellis/scripts/task.py validate 06-29-codex-clarification-routing
```

```text
OK: 06-29-codex-clarification-routing
```

```bash
git diff --check
```

```text
<no output>
```

```bash
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

```text
docs clarification routing checks OK
```

## BLOCKED_QUESTION Status

No `BLOCKED_QUESTION` remains. The task was documentation-only and had enough context to complete safely.

## Remaining Risks / Follow-ups

- No runtime router or board behavior was changed, by design.
- Avatar/Hermes should verify that future Codex goals include this policy when clarification risk is present.
