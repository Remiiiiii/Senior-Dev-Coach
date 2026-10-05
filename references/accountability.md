# Accountability design

Goal: whenever live development touches a gap in the plan, the developer is reminded of the open module task at the moment it matters, escalating when tasks are ignored. Only gaps in the user's plan speak; everything else is silent.

## Event -> rule -> gap

| Event | Rule | Fires when | Gap(s) |
|---|---|---|---|
| commit-msg | commit-message-quality | subject not `type(scope): why` | change-hygiene |
| commit-msg | fix-without-test | `fix` commit with source but no test staged | debugging-method, test-as-gate |
| pre-commit / agent-done | commit-files-cap | more files than cap (15 per commit, 40 per agent change) | change-hygiene |
| pre-commit / agent-done | risky-without-test | auth/tenant/billing-like source changed without tests | security-hygiene, test-as-gate |
| pre-commit / agent-done | src-without-test | >= 50 changed source lines, no tests | test-as-gate |
| pre-commit / agent-done | god-file-growth | file over 800 lines (or a baseline god file) grows > 20 lines | modular-architecture |
| pre-commit / agent-done / pre-push / ci | secret-in-diff | added line looks like a credential | security-hygiene, operational-predictability |
| agent-done / pre-push | blast-radius-note | large agent change, no `coach.py note` since last commit | ai-ownership |
| pre-push / ci | push-range-size | range over 800 lines or 40 files | change-hygiene, operational-predictability |
| prompt | prompt-contract | build-type prompt missing >= 2 of constraints, tests, scope | ai-ownership, requirements-clarity |

Thresholds live in `settings` inside the state file (`commit_file_cap`, `pr_line_cap`, `pr_file_cap`, `god_file_loc`, `risky_regex`); edit them to fit the codebase.

## Severity and enforcement

Rule weights: `soft`, `hard`, `critical`. Modes (global, or per gap via `plan.gaps.<id>.mode`):

- `nudge`: always warn, never block (except `critical`).
- `escalate` (default): warn; **block `hard` rules** when the gap has overdue tasks or the same gap produced >= 3 warnings in 7 days.
- `gate`: block every `hard` rule.
- `off`: silent for that gap.
- `critical` (secrets) blocks in every mode except `off`.

Mastered gaps are info-only; 3 info findings in 14 days reopen the gap.

## Overrides

`COACH_OVERRIDE="reason, 8+ chars" git commit ...` passes a block and writes an `override` ledger entry (gap, rule, reason). `coach.py status` shows overrides per gap over 30 days. Overrides are honest escape hatches, visible rather than forbidden.

## Known limits (be upfront with the developer)

- `git commit --no-verify` skips local hooks; the CI backstop (`integrations/github-action.yml`) re-checks size and secrets on PRs.
- Heuristics: "risky path" is a regex, "test" is a path pattern, "source" is an extension list. Tune them.
- A blocked hook only holds if the developer wants it to. The point is visibility and a paper trail, not policing.
- The state file is local and editable. It is a coaching tool, not an audit system.
