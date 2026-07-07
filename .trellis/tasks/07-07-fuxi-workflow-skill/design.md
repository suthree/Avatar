# Design

Avatar currently stores reusable skills/SOPs in `memory/*.md` and whitelists each tracked memory file in `.gitignore`. The repository does not have a separate tracked `skills/` tree.

Therefore the latest Hermes FuXi workflow is imported as:

```text
memory/fuxi_state_reporting_sop.md
```

The file starts with an Avatar integration note, then embeds the latest Hermes state-reporting workflow and the three recent references that matter for this request:

- branch normalization and UAT issue closure;
- BaiZe branch baseline cleanup and issue closure;
- FuXi Codex Tool SOP Layer.

This keeps the skill usable by Avatar without changing authority boundaries. Existing SOPs remain responsible for dev-workflowd and Codex dispatch rules.
