---
name: ai-native-development
version: 1.2
maintainer: vibe-coding-lab
homepage: https://github.com/znlm1229/vibe-coding-lab/tree/main/workflow-spec
last-validated-with: claude-opus-4-7
description: |
  A nine-stage workflow for AI-native software development — Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★ (★ = mandatory human gate).

  Use this skill whenever the user asks the AI to build a feature, implement a system, ship a product, scaffold a project, bootstrap an MVP, set up something from scratch, or do any non-trivial end-to-end coding work — even if they don't explicitly name the workflow. Trigger on phrases like "help me build X", "implement Y", "let's add a feature", "set up Z", "scaffold a project", "ship V1 of X", "end-to-end build", "from zero to ship", "design and build", "MVP for ...", "launch ..."

  中文触发场景：用户说 "帮我做 / 搭 / 建 / 实现 / 上线 / 端到端做完 / 从零搭 / 按工作流走一遍 X"、"MVP / 最小可用版本 X"、"一整套 X"、"做个 V1 of X" 时同样应触发。

  This workflow ORCHESTRATES OTHER SKILLS at specific stages: REQUIRES the 'grill-me' skill at Stage 2 and 'verification-before-completion' before Stage 8; RECOMMENDS 'brainstorming' at Stage 1, 'writing-plans' at Stage 5, and 'requesting-code-review' during Stage 8. Load this skill whenever a coding task is large enough to benefit from structured stages.

  When triggered for smaller tasks, explicitly downscope (announce which stages will be skipped and why) rather than mechanically running all nine stages.

  DO NOT trigger for trivial work: one-line bug fixes, renames, code formatting, pure markdown / docstring / changelog edits, dependency bumps, or pure config tweaks — these don't warrant the ceremony.
---

# AI-Native Development Workflow

> **v1.2** (2026-05-19) — validated end-to-end on a real ship; added 4 superpowers-skill bindings, AC verification discipline, auto-mode clarification, and 2 new failure modes captured from the v1.1 retrospective. Changelog at the bottom.

## What this skill is for

This skill defines how the AI should approach a coding task: not by jumping straight to writing code, but by moving through nine deliberate stages. The core philosophy is **alignment before code, verification before done**. Most failures in AI-assisted coding come from the AI confidently building the wrong thing, or building the right thing in a way nobody checked. This workflow front-loads thinking and back-loads human confirmation to prevent both.

## Stage cheat sheet

| Stage | Human gate? | Bound skill |
|---|---|---|
| 1 Brainstorm | | recommended: `brainstorming` |
| 2 Grill Me | | **required: `grill-me`** |
| 3 Prototype | | (skip when no real uncertainty) |
| 4 SPEC | ★ | — |
| 5 Plan | | recommended: `writing-plans` |
| 6 Tasks | ★ | — |
| 7 Implementation | | (before Stage 8 handoff) **required: `verification-before-completion`** |
| 8 Human QA | ★ | recommended: `requesting-code-review` |
| 9 Acceptance | ★ | — |

## How to run the workflow

Three rules govern movement through the workflow:

**Scale to the task.** A one-line bug fix does not need a Brainstorm or a Prototype. A new subsystem needs every stage. Before starting, judge the task's size and explicitly tell the user which stages you intend to run and which you'll skip, and why. Let them correct you.

**Stop at every human gate.** Four stages are hard stops where you must not proceed without explicit user confirmation in the chat: **SPEC** end (alignment on *what*), **Tasks** end (alignment on *how* and *scope*), **Human QA** (does it actually work), and **Acceptance** (confirmation against the contract). Producing the artifact is your job; approving it is the human's. Never approve your own SPEC or accept your own work.

**Make each stage produce a visible artifact.** Every stage ends with something concrete the user can read — a list of ideas, a list of hard questions, a running prototype, a SPEC document, a plan, a task list, a diff, a QA report, an acceptance checklist. "I thought about it" is not a stage output. If a stage's artifact would be trivial, say so and move on rather than padding it.

When you begin a task, briefly state the plan: which stages, in what order, where the human gates are. Then start with stage one.

## The nine stages

### 1. Brainstorm

Diverge before you converge. Generate multiple approaches, framings, and possibilities for the problem — not one anointed solution. The goal is to surface the option space so the user can see roads not taken.

**Recommended skill: `brainstorming`.** When available, prefer this skill to drive divergent thinking rather than ad-hoc listing — it forces more genuine option exploration before converging.

Output: a short list of distinct approaches, each with a one-line sketch of its core idea and its main tradeoff. Aim for 3–5. If the task genuinely has only one sensible approach, say that explicitly rather than inventing weak alternatives.

Do not evaluate to a winner yet — that is the user's call, informed by the next stage.

### 2. Grill Me

Pressure-test before you build. Take the leading idea (or ideas) and interrogate it: surface hidden assumptions, edge cases, failure modes, integration risks, and unanswered questions. The name is literal — the AI should grill the *idea*, and invite the user to grill back.

**Required tool: the `grill-me` skill.** This stage must be driven by invoking the `grill-me` skill, which relentlessly interviews the user about the plan or design, resolving each branch of the decision tree. Ad-hoc question-listing by the AI alone does not match the skill's coverage and is not an acceptable substitute. If the skill is unavailable in the current environment, stop and surface this to the user rather than silently falling back.

Output: a list of pointed questions and identified risks, grouped roughly by severity (distilled from the `grill-me` interaction). Each item should be specific enough to act on ("what happens to in-flight requests during the migration?" not "have we considered edge cases?"). The artifact must also include a short **skill invocation record**: when the skill was invoked, how many interview turns, and which key decision-tree branches were covered.

**Mark open questions by type (v1.2):** `technical` (objective decision with a correct answer) vs `taste` (subjective preference — AI's suggestion is a placeholder the user should personalize). Taste-type OQs should default to a "AI's draft is placeholder, please rewrite to match your voice" caveat in the SPEC.

End this stage by asking the user to answer the open questions, or to confirm which ones are acceptable to defer. Their answers feed the SPEC.

### 3. Prototype

Build the smallest rough thing that resolves the riskiest uncertainty. A prototype is throwaway by default — its job is to convert an open question into a settled answer, or to give the user something tangible to react to. It is not the implementation.

Output: a minimal running artifact (a script, a sketch, a spike branch) plus a one-paragraph note on what it proved or disproved.

Skip this stage when nothing is genuinely uncertain — when the path is clear, prototyping is just slower implementation. Say so and move on.

### 4. SPEC  *(human gate)*

Write down *what* will be built — not how. The SPEC captures the agreed scope: the behavior, the inputs and outputs, the boundaries, the explicit non-goals, and the acceptance criteria that Stage 9 will check against.

**AC verification discipline (v1.2):** Each acceptance criterion must specify both how AI verifies it and how a human verifies it — they are different channels, and the AC is only PASS when both signal yes. AI `grep` / `curl` / build-check can confirm string-level conditions; runtime behavior (clicks, toggles, JS-decoded content, animations, form submissions) needs a human in a browser. If you can't write a human verification path for an AC, the AC is probably not behavioral enough.

Output: a SPEC document. Use the structure in `references/spec-template.md`.

**This is a hard stop.** Present the SPEC and ask the user to confirm it before doing any planning. The acceptance criteria written here are a contract — Stage 9 (Acceptance) checks the result against *this* document, so it must be concrete and testable. If the user changes the SPEC later, that is fine, but it is a visible, deliberate act, not a silent drift.

### 5. Plan

Decide *how* and *in what order*. Working from the confirmed SPEC, lay out the technical approach, the sequence of work, the dependencies between pieces, and the risky parts that need care. The Plan answers "how will we get from nothing to the SPEC."

**Recommended skill: `writing-plans`.** This skill structures multi-step implementation plans with phase ordering, risk flagging, and test strategy — a stronger starting frame than ad-hoc planning.

Output: a plan document — architecture decisions, ordered phases, dependency notes, and a flag on anything still risky. See `references/plan-and-tasks.md`.

### 6. Tasks  *(human gate)*

Break the Plan into a list of concrete, individually completable work items. Each task should be small enough to track, verify, and — in principle — hand to a separate agent. Each task names what it touches and what "done" means for it.

Output: an ordered, checkable task list. See `references/plan-and-tasks.md`.

**This is a hard stop.** The task list is the last point where scope is cheap to change. Present it and get the user's confirmation before writing implementation code. Once they approve, this list is the unit of progress tracking through Stage 7.

### 7. Implementation

Build it. Work through the approved task list in order, completing one task at a time and marking progress against the list as you go. Stay inside the SPEC — if you discover the SPEC was wrong or incomplete, stop and raise it rather than quietly building something different. A discovered SPEC gap sends you back to Stage 4, not off-script.

**Commit conventions (v1.2):**
- New task work: `task-TX: ...`
- Stage transitions / artifacts: `stage-N: ...`
- Bug fix on already-completed task (typically after a Stage 8 finding): `fix(TX): ...` — do NOT just reuse `task-TX`; the prefix distinguishes "first pass" from "回路", keeping git history honest about iteration

**Required handoff to Stage 8: `verification-before-completion` skill.** Before declaring Stage 7 complete or claiming all ACs pass, invoke this skill. AI's "AC passes" assertions need to be backed by output of an actual verification command, not just an assertion. Without this discipline, string-match ACs can silently appear PASS while runtime behavior is broken (see Common failure modes below).

Output: the working code, plus the task list updated to show what's done. Keep changes reviewable — small, coherent commits mapped to tasks beat one giant diff.

### 8. Human QA  *(human gate)*

A human checks the result. This is distinct from automated tests, which the AI should also run — Human QA is a person actually exercising the thing: trying the feature, checking the experience, hitting the cases that automated tests miss. The AI's role here is to make QA easy: summarize what changed, list what to test, point at the relevant entry points, and report what automated checks already passed.

**Recommended skill: `requesting-code-review`.** This skill structures the QA-readiness summary so the human can scan it quickly and exercise what matters most — modeled on how engineers prepare a PR for review.

Output: a QA-readiness summary from the AI (what changed, how to exercise it, what's already tested), then the human's findings.

**This is a hard stop.** Do not declare the work done because tests pass. A person has to look. If they find blocking bugs, return to Stage 7 to fix (using `fix(TX):` commit prefix) and re-handoff.

### 9. Acceptance  *(human gate)*

Confirm against the contract. Walk through the SPEC's acceptance criteria from Stage 4, one by one, and check the built result against each. Acceptance is binary per criterion — met or not met — and the work is "done" only when the user agrees every criterion is met.

Output: a checklist mapping each SPEC acceptance criterion to met / not met, with evidence. If anything is unmet, it routes back to the appropriate earlier stage (usually Tasks or Implementation) rather than being waved through.

Acceptance is the user's decision, not the AI's. The AI presents the evidence; the human accepts.

## Auto-mode boundary (v1.2)

When the host environment is in "auto mode" (continuous autonomous execution), the AI should:
- Apply auto-mode to **routine decisions within stages** (e.g., picking which file to edit, which variable name to use, which library version)
- **NEVER apply auto-mode to human gates.** Stages 4, 6, 8, 9 still require explicit user confirmation. Auto-mode does not override a deliberately designed safety stop.
- When in doubt at a gate, ask. The cost of pausing for confirmation at a designed stop is low; the cost of bypassing one can be a wrong-built feature or an unaccepted ship.

## Common failure modes to avoid

- **Skipping straight to Implementation.** The most common and most expensive mistake. Even under time pressure, a quick SPEC and task list beats building the wrong thing fast.
- **Self-approving gates.** The AI writing a SPEC and then proceeding as if it were confirmed. The gates exist precisely because the AI's confidence is not the same as the user's agreement.
- **Invisible stages.** Claiming a stage happened without producing its artifact. If there's nothing to show, the stage didn't happen.
- **Silent SPEC drift.** Discovering mid-Implementation that the SPEC was wrong and just... building something else. Changing the SPEC is allowed; doing it silently is not.
- **Padding small tasks.** Forcing a trivial fix through nine ceremonial stages. Scale to the task — the workflow serves the work, not the reverse.
- **Treating "tests pass" as "done."** Automated tests are necessary, not sufficient. Stages 8 and 9 are human stages on purpose.
- **Marking string-match ACs as PASS without verifying behavior.** *(NEW v1.2 — observed in vibe-coding-lab task 001.)* An AC like "HTML must not contain plaintext email" can be `grep`-verified to pass while the actual user-facing email link is completely broken (script not loaded, fallback text永远显示). When an AC concerns runtime behavior (clicks, toggles, JS-decoded content, animations, form submissions), the AI's automated check is necessary but not sufficient. The AC artifact MUST specify a human-verification path, and Stage 8 MUST exercise it. `verification-before-completion` skill (Stage 7→8 handoff) is the structural cure.
- **SPEC written before the stack is chosen.** *(NEW v1.2.)* Writing detailed paths, URLs, or file conventions in the SPEC before picking the starter / framework guarantees later patches. Either lock the stack first in a lightweight pre-SPEC step, or accept and explicitly version-tag the resulting SPEC patches (`v1.0.1`, `v1.0.2` etc.) — never silently update them.

## Reference files

- `references/spec-template.md` — the structure for the Stage 4 SPEC document, including how to write testable acceptance criteria with both AI and human verification channels.
- `references/plan-and-tasks.md` — structures for the Stage 5 plan document and the Stage 6 task list.
- `references/tooling.md` — recommended tools and companion skills (including all v1.2 stage-bound skills) for each of the nine stages.

## Changelog

- **v1.2** (2026-05-19) — Add 3 more stage-skill bindings (`brainstorming` S1, `writing-plans` S5, `verification-before-completion` S7→S8, `requesting-code-review` S8). Add OQ type marking (technical / taste). Add AC dual-channel verification discipline. Add commit prefix `fix(TX):` for Stage-8 回路 bug fixes. Add auto-mode boundary section. Add 2 new failure modes from the 001 retrospective. Add frontmatter version/maintainer/homepage/last-validated-with. Add Chinese trigger phrases + anti-trigger to description. Add top-of-file stage cheat sheet.
- **v1.1** (2026-05-18) — Bind `grill-me` skill as required at Stage 2.
- **v1.0** — Initial nine-stage workflow definition with three human gates.
