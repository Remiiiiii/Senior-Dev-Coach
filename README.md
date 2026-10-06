<div align="center">

# Senior Dev Coach

**Evidence-based growth for software engineers: an agent skill that evaluates your real work, teaches from it, and keeps you accountable.**

[![CI](https://github.com/Remiiiiii/Senior-Dev-Coach/actions/workflows/ci.yml/badge.svg)](https://github.com/Remiiiiii/Senior-Dev-Coach/actions/workflows/ci.yml)
[![Security](https://github.com/Remiiiiii/Senior-Dev-Coach/actions/workflows/security.yml/badge.svg)](https://github.com/Remiiiiii/Senior-Dev-Coach/actions/workflows/security.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)
![Dependencies: 0](https://img.shields.io/badge/dependencies-0-brightgreen.svg)

[Install](INSTALL.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

</div>

---

An agent skill that works like a small LMS for becoming a senior developer.

1. **Evaluates** you against senior-engineer expectations from your **git history** and **AI chat history** over a window you choose (1, 4, 6 or 12 months), across the repos you pick.
2. **Turns the gaps into interactive modules** (lessons, quizzes, evidence-backed exercises) built from your own files and commits.
3. **Holds you accountable during live development**: git hooks, agent hooks and a CI backstop remind you of the open module task when you do something related to a gap, and escalate when tasks go overdue.
4. **Re-measures** at 30/60/90 days and shows score deltas.

Works as a skill in Claude Code, Cursor (2.4+), Codex CLI and Gemini CLI (all read `SKILL.md`), and with any shell-capable agent via `prompts/kickoff.md`.

## Quick start

Full steps: [INSTALL.md](INSTALL.md). Let your agent do it: [AGENT_TAKE_THE_WHEEL.md](AGENT_TAKE_THE_WHEEL.md).

```bash
git clone https://github.com/Remiiiiii/Senior-Dev-Coach ~/senior-dev-coach      # a template: never edit it
python3 ~/senior-dev-coach/scripts/coach.py init                              # links it into your agent; creates a stable shim
# then tell your agent: "Evaluate me as a developer"
```

The clone stays pristine. Everything personal (evaluation, plan, progress, reports, hook settings) lives in `~/.senior-coach/` on your machine, so `git pull` updates the template without touching your progress.

## The journey

1. **Install**: `init` injects the skill into Claude Code, Cursor, Codex or Gemini CLI.
2. **Discover**: a read-only scan finds your repos, git identities (work and personal) and chat exports; you confirm.
3. **Evaluate**: window of 1/4/6/12 months across your repos and chat history; scorecard with evidence, facts vs inferences, and what could not be assessed. Saved to `~/.senior-coach/reports/`.
4. **Learn**: lessons are chosen from *your* evidence and taught with techniques that fit how each gap closes (retrieval quizzes with spaced re-tests, worked examples, guided refactors, review drills, debug labs, explain-back, pre-mortems, katas, rewrites, live pairing, metric challenges).
5. **Stay accountable**: with your consent, git hooks, agent hooks and a CI backstop remind you of the open lesson when live work touches a gap. Starts as nudges, escalates after a week.
6. **Re-measure** at 30/60/90 days and compare scorecards.

## How it is put together

| Piece | Where | Deterministic? |
|---|---|---|
| Intake, scoring, report, teaching | `SKILL.md`, `references/rubric.md`, `report-template.md`, `module-spec.md`, `techniques.md` | No: the agent's judgment, with evidence rules |
| Git metrics (files/commit, message quality, test colocation, hotspots, god files, fix-after-ship, secrets, PR sizes) | `scripts/gitmetrics.py` | Yes |
| Chat metrics + redacted sample (Claude.ai, ChatGPT, JSONL, markdown) | `scripts/chatmetrics.py` | Yes (keyword heuristics; the agent reads the sample) |
| Gap library: detectors, techniques, evidence-gated tasks, success signals | `references/gap-library.json` | Yes |
| Install, discovery, plan state, progress, spaced reviews, verification, ledger | `scripts/coach.py` -> `~/.senior-coach/` | Yes |
| Live accountability | `coach.py check` + `integrations/` | Yes |

## Security by design

Because the skill is text an agent follows plus scripts that run locally, every pull request is treated as a potential supply-chain attack.

- **Zero runtime dependencies, no network access, local-only data.**
- **Trust boundary:** repo files, commit messages and chat history are data, never instructions (see `SKILL.md`).
- **Integrity guard** (`.github/scripts/guard.py`) blocks invisible Unicode, prompt-injection phrasing, `eval`/`exec`, network and shell-execution primitives, download-and-run, dependency manifests, symlinks, binaries and credential formats. In CI it runs from the **base branch**, so a PR cannot weaken the rules that judge it.
- **Hardened pipeline:** least-privilege tokens, no `pull_request_target`, actions pinned to commit SHAs, CodeQL, dependency review, Dependabot.
- **Governance:** CODEOWNERS on all trust-critical paths, signed commits, immutable release tags.

Details and threat model: [SECURITY.md](SECURITY.md). Maintainer checklist: [docs/REPOSITORY_SETTINGS.md](docs/REPOSITORY_SETTINGS.md).

## Privacy

Everything runs locally. Chat exports are parsed on your machine, secrets/emails/tokens/IPs/home paths are redacted, and only short excerpts reach the report. Secret scans report `{commit, file, kind}`, never the value. State is stored in `~/.senior-coach`, not in your repos. Only commits matching *your* identity are scored. Reports can still contain file paths and commit subjects: review before sharing.

## Limits worth knowing

- Metrics are heuristics (regexes for "risky" and "test" paths, keyword matching for chat). Tune thresholds in the state file's `settings`.
- Hooks can be bypassed (`--no-verify`); the GitHub Action re-checks PR size and secrets. The ledger makes overrides visible, it does not prevent them.
- The evaluation reflects habits visible in the data. It cannot see code review by others, production incidents, or whether you can design without AI.
- Agent hooks are Claude Code only (`UserPromptSubmit`, `Stop`; checked against the docs). Other agents get the skill plus git hooks and an optional rules file. A guard blocks the Stop hook once per identical diff to prevent loops.
- Personal Claude Code skills don't load in Cowork or cloud sessions.

## Develop

```bash
python3 -m unittest discover -s tests   # end-to-end pipeline + integrity guard tests
python3 -I .github/scripts/guard.py     # the same checks CI runs
```
See [CONTRIBUTING.md](CONTRIBUTING.md). To add a gap, rule or parser, use the prompt in `prompts/extend.md`. Suggested GitHub topics: `agent-skills`, `claude-code`, `developer-growth`, `engineering-metrics`, `git-hooks`.

MIT licensed.
