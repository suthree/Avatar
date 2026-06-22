# Avatar Documentation Index

Use this page as the entrypoint for stable project facts.

Core docs:

- `GA_CODEX_LOOP.md`: Avatar controller and Codex worker operating contract.
- `installation.md` / `installation_zh.md`: user installation and platform setup.
- `GETTING_STARTED.md`: beginner setup path.
- `SETUP_FEISHU.md`: Feishu bot setup.

Trellis split:

- `.trellis/workflow.md` defines the current Avatar workflow.
- `.trellis/spec/` stores executable rules for agents.
- `.trellis/tasks/` stores task-local plans, decisions, checklists, and verification.
- `.trellis/workspace/`, `.trellis/.developer`, and `.trellis/.runtime` are local-only and must not become task evidence.

Documentation should stay stable and user-readable. Active plans, temporary decisions, and in-flight checklists belong in Trellis tasks.

Migrated plans:

- The historical personal agent harness design and implementation plan now live in `.trellis/tasks/05-22-personal-agent-harness/`.
