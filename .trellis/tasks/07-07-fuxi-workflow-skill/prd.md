# PRD

## Goal

Add the latest Hermes FuXi workflow as an Avatar skill so future Avatar/FuXi work can reuse the current state-reporting, reset-recovery, branch/UAT closure, and Codex Tool SOP guidance.

## Scope

- Create a tracked Avatar memory skill for FuXi state reporting.
- Include the latest Hermes `fuxi-state-reporting` workflow content.
- Include recent references for branch normalization/UAT closure, BaiZe baseline cleanup, and Codex Tool SOP layering.
- Record the change as a Trellis task.

## Non-Goals

- No runtime behavior changes.
- No dev-workflowd, Codex, GitHub, or deployment automation changes.
- No secrets, session logs, local run directories, or environment-specific runtime state.

## Acceptance Criteria

- `memory/fuxi_state_reporting_sop.md` exists and is tracked.
- The new SOP explicitly complements existing FuXi boundary/dispatch SOPs.
- The source Hermes workflow and key references are preserved in Avatar-readable form.
- Validation and whitespace checks pass.
