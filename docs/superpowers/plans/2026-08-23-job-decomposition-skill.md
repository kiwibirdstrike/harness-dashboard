# Job Decomposition Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and install a conversational Codex skill that decomposes an overall project task into flat, independently assignable Job folders after explicit user approval.

**Architecture:** Keep the skill as one focused `SKILL.md` with no custom runtime or dependency. It conducts a one-question-at-a-time interview, produces a no-write proposal, preflights approved paths, then uses existing filesystem tools to create `JOBS.md`, flat Job folders, and zero-byte `AGENT.md` placeholders. The repository contains the distributable source; the same directory is installed as a personal Codex skill.

**Tech Stack:** Codex skill Markdown, YAML frontmatter, existing Codex filesystem tools, Git.

**Spec:** `docs/superpowers/specs/2026-08-23-job-decomposition-skill-design.md`

## Global Constraints

- One top-level folder represents one Job and one replaceable Agent assignment slot.
- Job structure must not depend on the Agent Pool or Agent product names.
- Job folders must be flat under the selected project root.
- Folder names use `NN_short_job_name`: two-digit prefixes, lowercase ASCII words, and underscores.
- Ask exactly one focused question per interview turn.
- Do not write before a final preview and explicit creation instruction.
- Creation produces one root `JOBS.md` and one zero-byte `AGENT.md` inside each approved Job folder.
- Never overwrite or silently merge existing `JOBS.md`, `AGENT.md`, or folders.
- Agent assignment and per-Job Harness authoring remain outside the skill.
- Add no dependency or helper runtime.

---

## File Structure

- Create `skills/job-decomposer/SKILL.md`: complete interview, decomposition, preview, preflight, creation, and reporting behavior.
- Modify `README.md`: purpose, installation, and invocation.
- Install `skills/job-decomposer/` to the personal Codex skills directory during execution; keep the repository copy as source of truth.

No helper script is planned. Existing filesystem tools cover the required behavior with less code and fewer interfaces.

---

### Task 1: Create the Conversational Job Decomposer Skill

**Files:**
- Create: `skills/job-decomposer/SKILL.md`
- Reference: `docs/superpowers/specs/2026-08-23-job-decomposition-skill-design.md`

**Interfaces:**
- Consumes: overall task, project root, and relevant existing files.
- Produces before approval: flat Job tree and complete `JOBS.md` preview, with no writes.
- Produces after approval: `JOBS.md`, approved Job folders, and zero-byte `AGENT.md` files.

- [ ] **Step 1: Read required skill-authoring instructions**

Read the complete `skill-creator` and `superpowers:writing-skills` instructions available in the execution environment. Follow their package, frontmatter, validation, and behavioral evaluation requirements.

- [ ] **Step 2: Write the initial skill**

Create `skills/job-decomposer/SKILL.md` with this content:

```markdown
---
name: job-decomposer
description: Use when a user wants to divide an overall project task into flat folders that each represent an independently assignable Agent Job, before Agent assignment or per-folder Harness design.
---

# Job Decomposer

Turn one overall project task into a reviewed set of independent Job folders. Plan conversationally first. Create files only after explicit final approval.

## Boundaries

- Treat one top-level folder as one Job and one replaceable Agent assignment slot.
- Ignore the available Agent Pool when deciding Job boundaries.
- Never recommend, select, or record an Agent product.
- Never create per-Job prompts, procedures, task instructions, or Harness content.
- Never use fixed research, planning, implementation, and review phases unless the actual Job boundaries independently require them.
- Never force a fixed folder count.

## Interview

1. Read the overall task and inspect only relevant existing project files.
2. Identify the single ambiguity that most affects Job boundaries.
3. Ask exactly one focused question and wait for the answer.
4. Repeat until each proposed Job has a distinct responsibility, deliverable, and completion condition.
5. Do not write files during the interview.

Split a Job when it can be independently assigned, has a distinct deliverable, forms a handoff, prevents ownership conflicts, can run in parallel, or can be reassigned without changing other Jobs.

Keep work together when it shares one continuous context and deliverable, has no meaningful intermediate completion state, would require repeated context reconstruction if split, or is too small to justify a separate assignment slot.

Use this deciding question:

> Would making this a separate Agent assignment slot produce a clearer responsibility and independently verifiable result?

## Proposal

Present:

1. a flat tree using `NN_short_job_name` folders;
2. responsibility, scope, deliverables, dependencies, parallel Jobs, completion conditions, and split reason for every Job;
3. the complete proposed `JOBS.md`;
4. every path that creation would add.

Let the user merge, split, rename, add, remove, and reorder Jobs. Re-render the full proposal after revisions. Folder names use two-digit numeric prefixes, lowercase ASCII words, and underscores. Numbers provide display and approximate dependency order; `JOBS.md` owns the actual dependency graph.

Approval of a question, Job, or draft is not creation approval. Wait until the final preview is visible and the user explicitly says to create it, such as `만들어` or `생성해`.

## JOBS.md Contract

Write `JOBS.md` in the user's language with this information:

```markdown
# Project Jobs

## Overall Goal

[Final project outcome]

## Job 01 — [Job title]

- Folder: `01_short_job_name`
- Objective: [Result owned by this Job]
- Scope: [Included work]
- Deliverables: [Required artifacts]
- Depends on: [Job folders or None]
- Can run in parallel with: [Job folders or None]
- Done when: [Observable completion conditions]
- Split reason: [Reason for an independent assignment slot]
```

Do not include Agent names, commands, assignments, or per-Job working instructions.

## Creation Safety

After explicit creation approval:

1. Resolve and display the project root.
2. Preflight `JOBS.md`, every Job folder, and every `AGENT.md` target.
3. If any target exists, write nothing. Report all conflicts and ask the user to rename, explicitly reuse an existing folder in a revised plan, revise the structure, or cancel.
4. Re-run the complete preflight after every revision.
5. Create only the paths in the approved final preview.
6. Write the approved `JOBS.md` content.
7. Create every `AGENT.md` as an empty, zero-byte file. Never write a heading, newline, comment, or template into it.
8. Report the resulting tree and verify every `AGENT.md` has size zero.

If an unexpected filesystem failure occurs after creation begins, report exactly which paths were created and which operation failed. Do not delete or modify pre-existing user content while recovering.
```

- [ ] **Step 3: Validate the skill package**

Run the validator required by `skill-creator`. Expected: valid YAML frontmatter, accepted skill name, and no missing required package files.

- [ ] **Step 4: Commit the initial skill**

```bash
git add skills/job-decomposer/SKILL.md
git commit -m "Make project decomposition follow Agent assignment boundaries" -m "Constraint: Job folders must stay flat and Agent-agnostic.\nRejected: Fixed phase templates | phases do not define independent ownership.\nConfidence: medium\nScope-risk: narrow\nDirective: Do not add per-Job Harness authoring to this skill.\nTested: Skill package validator.\nNot-tested: Behavioral scenarios run in Task 2."
```

---

### Task 2: Verify the Skill Through Behavioral Scenarios

**Files:**
- Modify if needed: `skills/job-decomposer/SKILL.md`
- Test workspace: a fresh temporary directory created by the skill-testing workflow.

**Interfaces:**
- Consumes: `job-decomposer` from Task 1 and controlled user scenarios.
- Produces: evidence for no-write planning, Agent-agnostic flat decomposition, approval-gated creation, collision safety, and zero-byte placeholders.

- [ ] **Step 1: Run the no-write interview scenario**

Prompt:

```text
이 프로젝트는 데이터 수집, API 구현, 웹 화면 구현, 통합 검증이 필요해. 작업 폴더 구조를 짜줘. 아직 만들지는 마.
```

Expected:

- asks at most one question;
- creates no `JOBS.md`, Job folder, or `AGENT.md`;
- names no Agent product;
- does not assume a fixed four-phase template.

- [ ] **Step 2: Run the same-chapter split scenario**

Follow-up:

```text
구현이라는 같은 챕터 안에 backend API, frontend UI, integration 세 책임이 있고 각각 독립 산출물과 완료 조건이 있어.
```

Expected proposal:

```text
01_backend_api/
02_frontend_ui/
03_system_integration/
```

It remains flat, explains three independent assignment slots, and avoids Agent names.

- [ ] **Step 3: Run the explicit-approval creation scenario**

After the final preview, send:

```text
이 최종안대로 만들어.
```

Expected filesystem:

```text
JOBS.md
01_backend_api/AGENT.md
02_frontend_ui/AGENT.md
03_system_integration/AGENT.md
```

Verify all three `AGENT.md` files exist with size `0` and no chapter wrapper exists.

- [ ] **Step 4: Run the conflict scenario**

In a fresh temporary project, pre-create `02_frontend_ui/`, then repeat the approved creation flow.

Expected:

- reports the conflict before writing;
- creates no `JOBS.md`, `01_backend_api/`, or `03_system_integration/`;
- does not modify `02_frontend_ui/`;
- requests a revised choice instead of merging or overwriting.

- [ ] **Step 5: Run the Harness-scope refusal scenario**

Prompt after a valid proposal:

```text
각 폴더 AGENT.md에 Codex와 Claude가 따라야 할 프롬프트도 같이 작성해줘.
```

Expected: explains that Agent selection and Harness content are outside this skill, keeps every `AGENT.md` empty, and offers only the approved Job structure.

- [ ] **Step 6: Fix only observed failures and re-run all scenarios**

For each failure, add the smallest instruction that prevents that failure. Re-run the failed scenario first, then all five scenarios. Do not add a helper script or dependency.

- [ ] **Step 7: Commit behavioral fixes if any**

If the skill changed:

```bash
git add skills/job-decomposer/SKILL.md
git commit -m "Keep Job decomposition inside its approved creation boundary" -m "Constraint: Planning remains no-write until explicit final approval.\nRejected: Automatic scaffolding during proposal | users must revise safely before creation.\nConfidence: high\nScope-risk: narrow\nDirective: Preserve one-question interviews and all-or-nothing preflight.\nTested: Five behavioral skill scenarios.\nNot-tested: Windows-specific filesystem rendering."
```

Do not make an empty commit when no change is needed.

---

### Task 3: Document, Install, and Re-Verify the Skill

**Files:**
- Modify: `README.md`
- Source: `skills/job-decomposer/SKILL.md`
- Install: personal Codex skills directory resolved by skill-authoring instructions.

**Interfaces:**
- Consumes: verified repository skill package.
- Produces: installation/invocation documentation and a personal skill usable in other projects.

- [ ] **Step 1: Document the skill in README**

Add:

```markdown
## Job Decomposer Skill

`skills/job-decomposer` contains a conversational Codex skill that divides an overall project task into flat, independently assignable Job folders. It proposes and revises the structure before writing. After explicit creation approval it creates `JOBS.md`, each approved Job folder, and an empty `AGENT.md` placeholder in every folder.

The skill does not select Agents or write per-Job Harness instructions. Install the repository skill as a personal Codex skill to use it across projects, then invoke `$job-decomposer` with the overall task and target project folder.
```

Use the installation command required by the applicable skill instructions rather than adding another installer.

- [ ] **Step 2: Install the repository skill**

Install `skills/job-decomposer/` into the resolved personal Codex skill location. Confirm the installed package matches the tracked repository source. Do not edit the installed copy independently.

- [ ] **Step 3: Verify discovery outside the repository**

In a fresh temporary project, invoke:

```text
$job-decomposer 이 프로젝트의 전체 작업을 독립적으로 배치 가능한 Job 폴더로 나눠줘. 아직 파일은 만들지 마.
```

Expected: the one-question-at-a-time interview starts and no files are written.

- [ ] **Step 4: Run repository checks**

```bash
.venv/bin/python -m unittest tests.test_harness -v
PYTHONPYCACHEPREFIX=/private/tmp/harness-dashboard-pycache .venv/bin/python -m compileall -q app.py harness tests
git diff --check
```

Expected: all tests pass, compileall exits `0`, and diff check has no output.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md
git commit -m "Make the Job decomposition skill reusable across projects" -m "Constraint: The repository copy remains the distributable source of truth.\nRejected: App-only integration | the skill must work before and outside Dashboard launch.\nConfidence: high\nScope-risk: narrow\nDirective: Keep installed copies synchronized from skills/job-decomposer.\nTested: Skill discovery, no-write invocation, Harness tests, compileall, diff check.\nNot-tested: Installation on Windows."
```

- [ ] **Step 6: Review and push**

Request a code/skill review against the design spec. Fix every Critical or Important finding, re-run affected scenarios and repository checks, then push all commits to `origin/main`. Keep the untracked workspace `AGENTS.md` excluded.
