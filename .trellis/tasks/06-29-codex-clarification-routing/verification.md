# Verification

Date: 2026-06-29

## Commands

```bash
python3 .trellis/scripts/task.py validate 06-29-codex-clarification-routing
```

Output:

```text
OK: 06-29-codex-clarification-routing
```

```bash
git diff --check
```

Output:

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

Output:

```text
docs clarification routing checks OK
```

## Result

All requested documentation checks passed. No runtime Python source files were modified.
