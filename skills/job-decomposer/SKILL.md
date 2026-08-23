---
name: job-decomposer
description: Use when a user wants to divide an overall project task into independently assignable Job folders, before Agent assignment or per-folder Harness design.
---

# Job Decomposer

Design a flat project structure where each top-level folder is one Job and one replaceable Agent assignment slot. Job boundaries follow independent responsibility, not project phases or Agent brands.

## Boundaries

- Ignore the available Agent Pool when dividing work.
- Do not select, recommend, or record Agent products.
- Do not create per-Job prompts, procedures, or Harness content.
- Do not force research/planning/implementation/review phases or a fixed folder count.
- Keep every Job folder directly under the selected project root.

## Interview Before Writing

Inspect only relevant existing files. If Job boundaries are unclear, identify the ambiguity with the greatest structural impact, ask exactly one focused question, and wait. Repeat until every Job has a distinct responsibility, deliverable, and completion condition.

Split work when an independent assignment slot clarifies ownership, produces a distinct deliverable, forms a handoff, enables parallel work, prevents file conflicts, or can be reassigned without changing other Jobs. Keep work together when it continuously shares one context and deliverable or is too small to justify separate assignment.

## Proposal Contract

Use folder names `NN_short_job_name`: two-digit order, lowercase ASCII, underscores, and no Agent names. Numbers are display and approximate dependency order; `JOBS.md` records actual dependencies.

Present all of the following without writing files:

1. Flat folder tree.
2. Each Job's objective, scope, deliverables, dependencies, parallel Jobs, completion conditions, and split reason.
3. Complete proposed `JOBS.md`.
4. Exact paths that creation would add.

Let the user merge, split, rename, add, remove, and reorder Jobs. Re-render the complete proposal after revisions.

Approval of a question or draft is not permission to write. After showing the final preview, wait for an explicit creation instruction such as `만들어` or `생성해`.

## JOBS.md Shape

Write in the user's language:

```markdown
# Project Jobs

## Overall Goal

<final project outcome>

## Job 01 — <job title>

- Folder: `01_short_job_name`
- Objective: <result owned by this Job>
- Scope: <included work>
- Deliverables: <required artifacts>
- Depends on: <Job folders or None>
- Can run in parallel with: <Job folders or None>
- Done when: <observable completion conditions>
- Split reason: <reason for an independent assignment slot>
```

## Creation Gate

After explicit creation approval:

1. Resolve and display the project root.
2. Preflight `JOBS.md`, every proposed Job folder, and every `AGENT.md` path.
3. If any target exists, write nothing. List every conflict and wait for a revised plan, explicit reuse decision, rename, or cancellation. Never silently merge.
4. Re-run the full preflight after revisions.
5. Create only the approved paths and write the approved `JOBS.md`.
6. Create each `AGENT.md` as an empty, zero-byte file—no heading, newline, comment, or template.
7. Verify the resulting tree and every `AGENT.md` file size.

If an unexpected failure occurs after writing starts, report exactly what was created and what failed. Do not delete or alter pre-existing content during recovery.

## Example

Three independently owned responsibilities inside one implementation chapter become three flat Jobs:

```text
01_backend_api/AGENT.md
02_frontend_ui/AGENT.md
03_system_integration/AGENT.md
```

This remains three Jobs even if one Agent is later assigned to two folders.

## Common Mistakes

| Mistake | Correction |
| --- | --- |
| Nesting Jobs under a chapter folder | Put every assignment slot at project root. |
| Naming folders after Agents | Name the responsibility or outcome. |
| Writing during the proposal | Wait for explicit approval after final preview. |
| Reusing an existing folder silently | Stop before all writes and resolve the conflict. |
| Filling `AGENT.md` | Leave it exactly zero bytes. |
