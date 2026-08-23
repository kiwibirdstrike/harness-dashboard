# Job Decomposition Skill Design

## Purpose

Create a conversational Codex skill that turns one overall project task into a set of independently assignable Jobs. The skill plans first and writes only after explicit user approval.

The skill organizes work for Harness Dashboard. It does not select Agents, assign Agents, or define how an Agent works inside a Job.

## Core Model

```text
1 top-level folder = 1 Job = 1 replaceable Agent assignment slot
```

A Job folder represents an independent responsibility, not a conventional project phase and not a specific Agent product. The same Agent may later be assigned to multiple Job folders, and the Agent assigned to a folder may change over time.

All Job folders are created directly under the selected project root so Harness Dashboard can display and launch them together.

## Scope

The skill must:

- inspect the project goal and relevant existing project structure;
- interview the user one question at a time when important details are missing;
- propose an appropriate Job decomposition;
- explain why each Job is separate;
- let the user merge, split, rename, add, remove, and reorder Jobs;
- present the final structure and `JOBS.md` content before writing;
- create files only after an explicit instruction such as `만들어` or `생성해`;
- create one root `JOBS.md` file;
- create flat top-level Job folders;
- create one zero-byte `AGENT.md` file inside each Job folder.

The skill must not:

- select or recommend an Agent for a Job;
- read the current Agent Pool to decide the Job structure;
- write Agent names or commands into folder names or `JOBS.md`;
- assign Agents in Harness Dashboard;
- create prompts, procedures, task instructions, or Harness content inside a Job;
- use fixed research/planning/implementation/review phases;
- force a fixed number of folders;
- create files during the interview or proposal stages.

## Conversation Flow

The skill uses a deep-interview-style conversation:

1. Read the user's overall task and inspect relevant existing files without modifying them.
2. Identify ambiguities that materially affect Job boundaries.
3. Ask exactly one focused question at a time.
4. Stop asking when the project can be divided into independently assignable Jobs.
5. Present a draft containing the flat folder tree, Job definitions, dependencies, parallel work, and split reasons.
6. Let the user revise the draft through conversation.
7. Present a final creation preview with every path and the complete proposed `JOBS.md`.
8. Wait for an explicit creation instruction.
9. Preflight every target for conflicts.
10. Create the approved structure and report the resulting tree.

Approval of an individual design section is not permission to write files. Only an explicit creation instruction after the final preview authorizes creation.

## Job Boundary Rules

Split work into separate Jobs when one or more of these are true:

- the work can be assigned independently;
- it has a distinct deliverable and completion condition;
- it forms a handoff where another Job consumes its result;
- a separate work boundary prevents ownership or file conflicts;
- it can run in parallel with other work;
- its assigned Agent could be replaced without substantially changing the other Jobs.

Keep work in one Job when one or more of these are true:

- the steps continuously share the same context and deliverable;
- the intermediate result has no independently meaningful completion state;
- splitting would force repeated context reconstruction;
- the task is too small to justify an independent assignment slot.

Do not split merely because work belongs to different conventional phases, file types, document chapters, or technologies. Do not merge merely because the same Agent may eventually perform both Jobs.

The governing question is:

> Would making this a separate Agent assignment slot produce a clearer responsibility and independently verifiable result?

## Naming Rules

Job folders use:

```text
NN_short_job_name
```

Rules:

- use two-digit numeric prefixes beginning with `01`;
- use lowercase ASCII words separated by underscores;
- describe the responsibility or outcome;
- do not include Agent product names;
- order numbers by approximate dependency and display order;
- document actual dependencies in `JOBS.md` rather than treating numbering as strict execution order.

Parallel Jobs still receive distinct numbers.

## Output Contract

An approved structure has this shape:

```text
project-root/
├── JOBS.md
├── 01_requirements_definition/
│   └── AGENT.md
├── 02_backend_api/
│   └── AGENT.md
├── 03_frontend_interface/
│   └── AGENT.md
└── 04_system_integration/
    └── AGENT.md
```

Every `AGENT.md` must be an empty, zero-byte file. It is a placeholder for a later, separate Harness-design process.

`JOBS.md` uses this structure:

```markdown
# Project Jobs

## Overall Goal

The final project outcome.

## Job 01 — Requirements Definition

- Folder: `01_requirements_definition`
- Objective: The result owned by this Job.
- Scope: Work included in this Job.
- Deliverables: Artifacts this Job must produce.
- Depends on: Earlier Jobs, or `None`.
- Can run in parallel with: Other Jobs, or `None`.
- Done when: Observable completion conditions.
- Split reason: Why this deserves an independent assignment slot.
```

The generated document may use the user's language, but folder names remain lowercase ASCII for portable CLI use.

## Conflict and Failure Handling

Before writing, the skill checks every proposed path.

- Never overwrite an existing `JOBS.md` or `AGENT.md`.
- Never silently merge a proposed Job with an existing folder.
- If any target conflicts, write nothing and present the conflicts.
- Ask the user to rename the Job, reuse the existing folder explicitly, revise the plan, or cancel.
- Re-run the complete preflight after any revision.
- Create only paths shown in the approved final preview.
- If an unexpected filesystem failure occurs after creation starts, report exactly what was created and what failed. Do not delete pre-existing user content while recovering.

## Example

For one implementation chapter containing backend, frontend, and integration responsibilities, a valid decomposition is:

```text
01_backend_api/
02_frontend_interface/
03_system_integration/
```

This remains three Jobs even if the same Agent is later assigned to backend and integration. The folders represent independent assignment slots, not unique Agent identities.

## Acceptance Criteria

- The skill interviews before proposing when Job boundaries are ambiguous.
- It asks one question per turn.
- It proposes Jobs without consulting or naming available Agents.
- The proposal is flat and contains no chapter wrapper folders.
- The user can revise the proposal without filesystem changes.
- No write occurs before an explicit final creation instruction.
- Conflict preflight prevents partial writes caused by known path collisions.
- Creation produces one `JOBS.md`, the approved Job folders, and one zero-byte `AGENT.md` per folder.
- Existing files are never overwritten.
- Agent assignment and per-Job Harness content remain outside the skill's scope.
