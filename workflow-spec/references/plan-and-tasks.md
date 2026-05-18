# Plan & Tasks (Stages 5 and 6)

## Stage 5: The Plan

The Plan answers **how** and **in what order** — it turns the confirmed SPEC into a technical route. Where the SPEC is the destination, the Plan is the path.

Use this structure:

```markdown
# Plan: [Feature / system name]

## Approach
The overall technical strategy in a few sentences. The key architecture
decision(s) and why this approach over the alternatives raised in Brainstorm.

## Phases
An ordered list of phases. Each phase is a meaningful, coherent chunk of
progress — not yet individual tasks. For each:
- What it delivers
- Why it comes where it does in the order

## Dependencies
What depends on what. Call out anything that blocks parallel work, anything
that touches shared/fragile code, anything that needs an external input.

## Risks
The parts most likely to go wrong, and how the plan mitigates them. If a
Prototype (Stage 3) settled a risk, note that here. Remaining unknowns get
flagged loudly.

## Test strategy
How the result will be verified — what gets unit tested, what gets
integration tested, and what is left for Human QA (Stage 8) because it
needs a person.
```

## Stage 6: The Tasks

Tasks break the Plan into individually completable work items. This is the **last cheap point to change scope**, and it's a hard human gate.

A good task:
- Is small enough to complete and verify on its own
- Could, in principle, be handed to a separate agent with just the SPEC and Plan as context
- Names what it touches (files, modules, surfaces)
- States its own "done" — usually one or two checkable conditions
- Is ordered relative to the others (dependencies respected)

Use this structure:

```markdown
# Tasks: [Feature / system name]

- [ ] **T1 — [short name]**
  Touches: [files / modules]
  Done when: [checkable condition]
  Depends on: [other tasks, or "nothing"]

- [ ] **T2 — [short name]**
  Touches: ...
  Done when: ...
  Depends on: T1
```

## Task sizing guidance

- If a task's "done when" needs more than two conditions, it's probably two tasks.
- If you can't say what files a task touches, the Plan isn't detailed enough yet — go back.
- If a task can't be verified without first completing three other tasks, the ordering or the breakdown is wrong.
- Prefer more, smaller tasks over fewer, larger ones — small tasks make Implementation progress visible and reviewable.

## Using the task list in Implementation

Once the user confirms the task list, it becomes the unit of progress tracking for Stage 7. Work through it in order, complete one task at a time, and mark each task done as you finish it — keeping the list a live, accurate picture of where things stand. Map commits to tasks so the diff stays reviewable.
