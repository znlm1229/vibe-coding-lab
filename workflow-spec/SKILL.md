---
name: ai-native-development
description: A nine-stage workflow for AI-native software development — Brainstorm, Grill Me, Prototype, SPEC, Plan, Tasks, Implementation, Human QA, Acceptance. Use this skill whenever the user asks the AI to build a feature, implement a system, ship a product, or do any non-trivial coding work, even if they don't explicitly name the workflow. It enforces thinking and alignment before code, and human verification before "done." Trigger it on requests like "help me build X", "implement Y", "let's add a feature", "code up Z", or any time a coding task is large enough to benefit from structured stages rather than jumping straight to writing code.
---

# AI-Native Development Workflow

## What this skill is for

This skill defines how the AI should approach a coding task: not by jumping straight to writing code, but by moving through nine deliberate stages. The core philosophy is **alignment before code, verification before done**. Most failures in AI-assisted coding come from the AI confidently building the wrong thing, or building the right thing in a way nobody checked. This workflow front-loads thinking and back-loads human confirmation to prevent both.

The nine stages are: **Brainstorm → Grill Me → Prototype → SPEC → Plan → Tasks → Implementation → Human QA → Acceptance**.

## How to run the workflow

Default to running the stages in order, but stay pragmatic. Three rules govern movement through the workflow:

**Scale to the task.** A one-line bug fix does not need a Brainstorm or a Prototype. A new subsystem needs every stage. Before starting, judge the task's size and explicitly tell the user which stages you intend to run and which you'll skip, and why. Let them correct you.

**Stop at every human gate.** Three stages are hard stops where you must not proceed without explicit user confirmation in the chat: the end of **SPEC** (alignment on *what*), the end of **Tasks** (alignment on *how* and *scope*), and **Human QA / Acceptance** (confirmation it actually works). Producing the artifact is your job; approving it is the human's. Never approve your own SPEC or accept your own work.

**Make each stage produce a visible artifact.** Every stage ends with something concrete the user can read — a list of ideas, a list of hard questions, a running prototype, a SPEC document, a plan, a task list, a diff, a QA report. "I thought about it" is not a stage output. If a stage's artifact would be trivial, say so and move on rather than padding it.

When you begin a task, briefly state the plan: which stages, in what order, where the human gates are. Then start with stage one.

## The nine stages

### 1. Brainstorm

Diverge before you converge. Generate multiple approaches, framings, and possibilities for the problem — not one anointed solution. The goal is to surface the option space so the user can see roads not taken.

Output: a short list of distinct approaches, each with a one-line sketch of its core idea and its main tradeoff. Aim for 3–5. If the task genuinely has only one sensible approach, say that explicitly rather than inventing weak alternatives.

Do not evaluate to a winner yet — that is the user's call, informed by the next stage.

### 2. Grill Me

Pressure-test before you build. Take the leading idea (or ideas) and interrogate it: surface hidden assumptions, edge cases, failure modes, integration risks, and unanswered questions. The name is literal — the AI should grill the *idea*, and invite the user to grill back.

**Required tool: the `grill-me` skill.** This stage must be driven by invoking the `grill-me` skill, which relentlessly interviews the user about the plan or design, resolving each branch of the decision tree. Ad-hoc question-listing by the AI alone does not match the skill's coverage and is not an acceptable substitute. If the skill is unavailable in the current environment, stop and surface this to the user rather than silently falling back.

Output: a list of pointed questions and identified risks, grouped roughly by severity (distilled from the `grill-me` interaction). Each item should be specific enough to act on ("what happens to in-flight requests during the migration?" not "have we considered edge cases?"). The artifact must also include a short **skill invocation record**: when the skill was invoked, how many interview turns, and which key decision-tree branches were covered.

End this stage by asking the user to answer the open questions, or to confirm which ones are acceptable to defer. Their answers feed the SPEC.

### 3. Prototype

Build the smallest rough thing that resolves the riskiest uncertainty. A prototype is throwaway by default — its job is to convert an open question into a settled answer, or to give the user something tangible to react to. It is not the implementation.

Output: a minimal running artifact (a script, a sketch, a spike branch) plus a one-paragraph note on what it proved or disproved.

Skip this stage when nothing is genuinely uncertain — when the path is clear, prototyping is just slower implementation. Say so and move on.

### 4. SPEC  *(human gate)*

Write down *what* will be built — not how. The SPEC captures the agreed scope: the behavior, the inputs and outputs, the boundaries, the explicit non-goals, and the acceptance criteria that Stage 9 will check against.

Output: a SPEC document. Use the structure in `references/spec-template.md`.

**This is a hard stop.** Present the SPEC and ask the user to confirm it before doing any planning. The acceptance criteria written here are a contract — Stage 9 (Acceptance) checks the result against *this* document, so it must be concrete and testable. If the user changes the SPEC later, that is fine, but it is a visible, deliberate act, not a silent drift.

### 5. Plan

Decide *how* and *in what order*. Working from the confirmed SPEC, lay out the technical approach, the sequence of work, the dependencies between pieces, and the risky parts that need care. The Plan answers "how will we get from nothing to the SPEC."

Output: a plan document — architecture decisions, ordered phases, dependency notes, and a flag on anything still risky. See `references/plan-and-tasks.md`.

### 6. Tasks  *(human gate)*

Break the Plan into a list of concrete, individually completable work items. Each task should be small enough to track, verify, and — in principle — hand to a separate agent. Each task names what it touches and what "done" means for it.

Output: an ordered, checkable task list. See `references/plan-and-tasks.md`.

**This is a hard stop.** The task list is the last point where scope is cheap to change. Present it and get the user's confirmation before writing implementation code. Once they approve, this list is the unit of progress tracking through Stage 7.

### 7. Implementation

Build it. Work through the approved task list in order, completing one task at a time and marking progress against the list as you go. Stay inside the SPEC — if you discover the SPEC was wrong or incomplete, stop and raise it rather than quietly building something different. A discovered SPEC gap sends you back to Stage 4, not off-script.

Output: the working code, plus the task list updated to show what's done. Keep changes reviewable — small, coherent commits mapped to tasks beat one giant diff.

### 8. Human QA  *(human gate)*

A human checks the result. This is distinct from automated tests, which the AI should also run — Human QA is a person actually exercising the thing: trying the feature, checking the experience, hitting the cases that automated tests miss. The AI's role here is to make QA easy: summarize what changed, list what to test, point at the relevant entry points, and report what automated checks already passed.

Output: a QA-readiness summary from the AI (what changed, how to exercise it, what's already tested), then the human's findings.

**This is a hard stop.** Do not declare the work done because tests pass. A person has to look.

### 9. Acceptance

Confirm against the contract. Walk through the SPEC's acceptance criteria from Stage 4, one by one, and check the built result against each. Acceptance is binary per criterion — met or not met — and the work is "done" only when the user agrees every criterion is met.

Output: a checklist mapping each SPEC acceptance criterion to met / not met, with evidence. If anything is unmet, it routes back to the appropriate earlier stage (usually Tasks or Implementation) rather than being waved through.

Acceptance is the user's decision, not the AI's. The AI presents the evidence; the human accepts.

## Common failure modes to avoid

- **Skipping straight to Implementation.** The most common and most expensive mistake. Even under time pressure, a quick SPEC and task list beats building the wrong thing fast.
- **Self-approving gates.** The AI writing a SPEC and then proceeding as if it were confirmed. The gates exist precisely because the AI's confidence is not the same as the user's agreement.
- **Invisible stages.** Claiming a stage happened without producing its artifact. If there's nothing to show, the stage didn't happen.
- **Silent SPEC drift.** Discovering mid-Implementation that the SPEC was wrong and just... building something else. Changing the SPEC is allowed; doing it silently is not.
- **Padding small tasks.** Forcing a trivial fix through nine ceremonial stages. Scale to the task — the workflow serves the work, not the reverse.
- **Treating "tests pass" as "done."** Automated tests are necessary, not sufficient. Stages 8 and 9 are human stages on purpose.

## Reference files

- `references/spec-template.md` — the structure for the Stage 4 SPEC document, including how to write testable acceptance criteria.
- `references/plan-and-tasks.md` — structures for the Stage 5 plan document and the Stage 6 task list.
- `references/tooling.md` — recommended tools and companion skills for each of the nine stages.
