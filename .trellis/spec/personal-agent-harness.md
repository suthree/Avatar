# Personal Agent Harness

The personal agent harness is Avatar's thin control plane direction. It must preserve the GenericAgent kernel instead of turning the repo into a large agent OS.

## Core Boundary

- `agent_loop.py` owns the minimal LLM turn loop and tool dispatch.
- Frontends and harness modules own session lifecycle, run records, cancellation, recovery, and worktree leases.
- Capabilities such as MCP, skills, scripts, providers, and external workers must declare scope, permissions, and verification before enablement.
- Memory promotion must go through evidence and review; normal task runs must not write global memory directly.

## Implementation Rules

- Do not modify `agent_loop.py` for the first harness milestone.
- Do not require GitHub Issues for every personal task.
- Do not require a daemon.
- Do not install dependencies unless explicitly approved.
- Do not enable MCP or skills implicitly.
- Keep stores file-backed and standard-library first.
- Development-task worktrees must be opt-in and isolated from the main checkout.
- When the harness allocates local development worktrees for Avatar, the default root is `.worktree/` under the project root.

## Trellis Link

The migrated design and implementation plan live in `.trellis/tasks/05-22-personal-agent-harness/`. Treat that task as historical planning input until a new implementation task is opened or resumed.
