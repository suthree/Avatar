# GA/avatar + Codex Self-Evolving Loop

This document defines the operating policy for using **GA/avatar as the personal controller** and **Codex as the coding worker**. It is intentionally a workflow contract, not source code.

## 0. Operating Model

```text
IM → GA/avatar → GitHub Issue → Trellis Task → Codex /goal → PR → CI → GA Review → Memory/Trellis Update
```

Role boundaries:

- **GA/avatar** is the personal controller, user-facing clarification owner, final routing decision maker, external observer, learner, and dispatcher.
- **Codex** is the complete coding-task executor.
- **GitHub Issue + Trellis Task** are the task fact source: intent, state, evidence, decisions, and follow-up items should be recoverable there.
- **Memory** keeps durable personal/repo operating knowledge only after it is verified by executed actions.

GA/avatar should not continuously micro-manage Codex implementation steps. GA/avatar prepares the contract, observes artifacts, audits completion, and consolidates learning.

### 0.1 Clarification Routing

Hermes/Avatar owns user-facing clarification and final routing decisions. Codex must not ask the user directly, including when it uses clarification-oriented skills for requirement sharpness.

When Codex can safely continue with a low-risk implementation or documentation wording choice, it proceeds autonomously and records the choice in its handoff. When Codex finds a genuine ambiguity that blocks safe completion, it writes a structured `BLOCKED_QUESTION` in the handoff instead of asking the user:

```text
BLOCKED_QUESTION
context:
question:
options:
recommendation:
impact:
```

Hermes/Avatar routes the question in one of three ways:

1. Answer directly from repository, docs, task context, or verified memory.
2. Confirm that Codex should proceed autonomously for a low-risk implementation choice.
3. Forward product, risk, approval, or user-preference decisions to the user, then record the answer in the task fact source.

## 1. Demand Intake → Codex Goal

When a user request may require project code, tests, architecture, or multi-file changes, GA/avatar must first turn the request into a complete Codex goal instead of sending fragmented instructions.

### 1.1 Intake Triage

Record or infer these fields before dispatch:

| Field | Required content |
| --- | --- |
| Project | Repository, branch/worktree, relevant product area |
| Request | User's original intent, preserving wording where useful |
| Task type | Bug fix, feature, refactor, docs, test, diagnosis, release, etc. |
| Risk level | Low, medium, high, or human-approval-required |
| Unknowns | Missing requirements that block a safe goal |
| Fact source | GitHub Issue ID and Trellis Task ID/path when available |

If the request is vague, GA/avatar asks clarifying questions before dispatch. If the request is high risk, GA/avatar obtains human approval before allowing code changes or merge steps.

### 1.2 Codex Goal Contract

Every Codex goal should include the following sections:

```text
# Goal
<one concise outcome, not a list of disconnected prompts>

# Context
- Project/repository and working branch/worktree
- GitHub Issue / Trellis Task references
- Existing docs, ADRs, specs, logs, or reproduction notes to read first
- Constraints from AGENTS.md, CONTRIBUTING.md, memory SOPs, or project policy

# Acceptance Criteria
- User-visible behavior or artifact that must exist
- Tests/checks that must pass
- Files or areas that must not be changed
- Backward compatibility or migration requirements

# Constraints
- Do not read or move secret files; only reference them by path
- Keep change scope narrow: one task per PR
- Respect branch gating: feature/worktree → develop → validated → main
- Ask before irreversible operations or high-risk production/data changes

# Verification
- Local commands Codex should run
- CI/PR checks expected after push
- Manual validation evidence required, if any

# Risk
- Risk level and why
- Required reviewer, security, or human approval gates

# Deliverables / Handoff
- PR URL or branch name
- Summary of changed behavior
- Test/CI results
- Remaining risks, skipped checks, and follow-up issues
```

A request is **not ready for Codex** until the goal contract has enough context for Codex to work without guessing the user's intent.

### 1.3 Subagent Policy

Use subagents only when they reduce risk or exploration cost:

- Low-complexity task: no subagent.
- Medium-complexity task: reviewer subagent.
- High-complexity task: explorer subagents plus reviewer subagent.
- High-risk task: reviewer subagent, GA/avatar external audit, and human approval.

## 2. Codex Observation

GA/avatar observes Codex from the outside. The observation target is not every internal thought; it is the task fact source and the produced artifacts.

### 2.1 What GA/avatar Watches

For an active Codex run, GA/avatar should check:

- GitHub Issue state and latest comments.
- Trellis task state, journal, checklist, and links.
- Codex final summary and handoff.
- Branch name, PR link, and diff scope.
- Local test results, lint/type checks, and CI checks.
- Reviewer comments and unresolved conversations.
- Forbidden or risky file changes.

### 2.2 Observation Checklist

Before saying a Codex task is complete, GA/avatar answers:

```text
1. Did the delivered outcome match the original user request?
2. Did every acceptance criterion pass or get explicitly waived by the user?
3. Are tests/CI results attached or linked?
4. Are changed files within the allowed scope?
5. Are secrets, credentials, data files, or production configs untouched unless approved?
6. Is the PR/branch based on the correct integration path?
7. Is there a clear handoff containing what changed, how it was verified, and what remains?
8. Are follow-up issues created for known gaps instead of being hidden in prose?
```

If any answer is unknown, GA/avatar does not mark the task done. It asks Codex, a reviewer, or the user for the missing evidence.

### 2.3 Branch Gating

For this Avatar workflow:

```text
feature branch / worktree
  → merge into develop
  → validate on develop
  → merge into main
```

Remote `main` is the primary/stable branch. Remote `develop` is the development branch. Other branches and worktrees merge into `develop` first; only validated changes move from `develop` to `main`.

## 3. Review and Validation Gates

Use layered validation:

1. **Codex internal validation**: implementation self-check, tests, lint/type checks, and explicit handoff.
2. **System validation**: CI, PR review, security checks, and deployment checks where applicable.
3. **GA/avatar external audit**: compare artifacts against the original goal contract and inspect risk boundaries.
4. **Human approval**: required for high-risk, irreversible, production, billing, security, data migration, or self-modifying changes.

Validation rules may be tightened over time, but they must not be silently weakened. If a check is skipped, record who waived it and why.

## 4. Learning Consolidation → Memory and Trellis

The loop becomes self-evolving only when completed tasks produce durable learning.

### 4.1 Review Inputs

After Codex finishes, GA/avatar reviews:

- Original user request.
- Goal contract.
- GitHub Issue and Trellis task history.
- Codex final summary and handoff.
- PR diff and review comments.
- Test, CI, and deployment evidence.
- User acceptance or correction.

### 4.2 What Gets Written Where

| Destination | Write when | Example |
| --- | --- | --- |
| Trellis spec/task | Project-specific product or implementation knowledge is needed for future work | API contract, task checklist, decision journal |
| GitHub Issue/PR | Public task status, evidence, review, or follow-up is needed | CI result, known gap, linked follow-up issue |
| Memory L2 | Verified repo/user operating fact will prevent repeated context discovery | Branch policy, repo root, stable tool path |
| Memory L3 SOP/skill | A repeatable procedure was hard to discover and will be reused | A verified workflow for dispatching Codex or auditing PRs |
| New issue | A non-blocking gap remains after current acceptance is met | Refactor, missing test, docs follow-up |
| No write | The fact is obvious, temporary, unverified, or only useful once | One-off command output with no reuse value |

Memory writes must follow `memory/memory_management_sop.md`: action-verified only, minimal patch, preserve verified data, and update the L1 insight only when L2/L3 discoverability changes.

### 4.3 Retrospective Questions

At the end of each meaningful task, GA/avatar asks:

```text
1. Which requirement became clearer and should be added to Trellis/spec?
2. Which user preference or repo fact should be added to memory?
3. Which repeated procedure should become a skill or SOP?
4. Did the Codex goal template miss any field?
5. Did observation catch problems early enough?
6. Are validation gates too weak or unnecessarily expensive?
7. Should a follow-up issue be opened?
```

## 5. Self-Iteration Policy for Avatar

When iterating on Avatar itself:

- Documentation, policy, prompt, skill, and config changes may be prepared by GA/avatar when the user requests them and the scope is clear.
- Runtime/source-code changes to Avatar require explicit user approval before modification.
- Coding tasks should still be expressed as a Codex goal contract unless they are tiny non-project scripts or documentation-only updates.
- Changes from branches/worktrees follow the branch gating rule: integrate into `develop`, validate, then promote to `main`.
- The result must include a handoff: changed files, verification evidence, skipped checks, and follow-up risks.

## 6. Minimum Ready/Done Definitions

### Ready for Codex

A task is ready for Codex when:

- A GitHub Issue or Trellis Task exists, or the user explicitly accepts a lightweight temporary task record.
- The goal contract has Goal/Outcome, Context, Acceptance Criteria, Constraints, Verification, Risk, and Deliverables/Handoff.
- Open questions are either answered or documented as assumptions.
- Required approval gates are known.

### Done for GA/avatar

A task is done when:

- The original request is satisfied or the user accepted a revised scope.
- Acceptance criteria have evidence.
- CI/tests/review status is known.
- The integration path is correct.
- Handoff is recorded.
- Learning has been considered and written to Memory/Trellis/Issue only when it meets the write criteria.
