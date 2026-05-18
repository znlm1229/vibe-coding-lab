# SPEC Template (Stage 4)

The SPEC describes **what** will be built, never **how**. It is the contract that Stage 9 (Acceptance) checks the finished work against, so every part of it must be concrete enough to verify.

Use this exact structure:

```markdown
# SPEC: [Feature / system name]

## Summary
One or two sentences. What is this and who is it for.

## Problem
What problem does this solve. Why now. What happens if we don't build it.

## Goals
The specific outcomes this work must achieve. Each goal should be observable.

## Non-goals
What this work explicitly does NOT cover. This section prevents scope creep
and is as important as the Goals section — be generous with it.

## Behavior
The expected behavior in concrete terms:
- Inputs: what goes in, in what form
- Outputs: what comes out, in what form
- Key flows: the main paths a user or caller takes
- Edge cases: known boundary conditions and how they should behave
- Error handling: what should happen when things go wrong

## Constraints
Hard limits the solution must respect — performance budgets, compatibility
requirements, security or compliance rules, deadlines, dependencies that
can't change.

## Open questions
Anything still unresolved. Ideally empty by the time the SPEC is confirmed —
if not empty, each item needs an owner and a resolution plan.

## Acceptance criteria
A numbered list of testable statements. Stage 9 checks the built result
against this list, one by one, so each must be unambiguously met-or-not-met.

Good:   "A logged-out user visiting /dashboard is redirected to /login."
Bad:    "Authentication works well."

Good:   "p95 response time for the search endpoint is under 200ms with 10k records."
Bad:    "Search is fast."

Each criterion should be checkable by someone who did not build the feature.
```

## Writing testable acceptance criteria

The single most important part of the SPEC. A criterion is testable when two different people checking it would reach the same verdict.

- State a **condition** and an **expected result**, not a quality adjective.
- Prefer observable behavior ("the file appears in the list") over internal state ("the cache is updated") unless the internal state is the deliverable.
- Make each criterion independent — one criterion, one thing to check.
- Quantify anything quantifiable — counts, times, sizes, limits.
- If a criterion can't be made testable, it probably belongs in Goals or Behavior as context, not in Acceptance.

## Keeping the SPEC honest

The SPEC is a hard gate. Present it to the user and wait for explicit confirmation before moving to Plan. If during later stages the SPEC turns out to be wrong or incomplete, return here, change it visibly, and get re-confirmation — never let the implementation quietly diverge from the written SPEC.
