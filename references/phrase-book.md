# Phrase book — what to say to your agent

Say these in plain English to your AI agent (Cursor, Claude Code, Codex, Gemini). The agent follows `SKILL.md` and runs the matching `senior-coach` / `coach.py` commands. You can also run the CLI yourself after `init` (shim: `~/.senior-coach/bin/senior-coach`).

**Tip:** “chapter”, “lesson”, “module”, and “task” all mean the next learning unit. Prefer **lesson** or **next**.

---

## First time / install

| You say | What happens |
|---|---|
| *Install Senior Dev Coach* / *Set up senior-dev-coach* | Agent follows `AGENT_TAKE_THE_WHEEL.md` or `INSTALL.md`; runs `init` |
| *Evaluate me as a developer* / *How senior am I?* / *Coach me* | Intake → discover → collect → scorecard → plan → first lesson |
| *Show me the phrase book* / *What can I ask you?* | Agent opens this file and summarizes |

CLI: `senior-coach init` · `senior-coach discover`

---

## Learning loop (day to day)

| You say | What happens | CLI |
|---|---|---|
| *What's next?* / *Next lesson* / *Next chapter* / *Continue* | Due reviews first, then the next open task; agent teaches it | `senior-coach next` |
| *Start this lesson* / *Begin the task* | Marks the current task in progress | `senior-coach task <gap> <id> start` |
| *I finished* / *Mark it done* (+ evidence: commit, PR, quiz result) | Records completion; schedules spaced reviews for quiz tasks | `senior-coach task <gap> <id> done --note "..."` |
| *I did the review* / *Re-test done* | Records a spaced review | `senior-coach task <gap> <id> review --note "..."` |
| *Show this module* / *Open gap change-hygiene* | Lists tasks for that gap | `senior-coach module <gap>` |
| *I'm stuck* / *Hint* / *Explain again* | Short re-teach on your code; does **not** mark done for you | — |
| *Skip this for now* | Agent leaves it open; picks another if you ask *what's next* | — |

---

## Progress and status

| You say | What happens | CLI |
|---|---|---|
| *How am I doing?* / *Status* / *Progress* | Plan summary: gaps, overdue, reviews due | `senior-coach status` |
| *Show my report* / *Scorecard* | Latest evaluation summary + path to full report | `senior-coach report` |
| *What gaps am I working on?* | Walks the plan gaps in plain language | `senior-coach status` |
| *Am I overdue?* | Lists overdue tasks and what to do | `senior-coach next` / `status` |

---

## Accountability (hooks)

| You say | What happens | CLI |
|---|---|---|
| *Turn on git hooks for this repo* | Installs commit / pre-push checks (**asks consent first**) | `senior-coach install-hooks --repo PATH` |
| *Turn on agent hooks* | Wires prompt / stop checks into your agent | `senior-coach integrate --agent …` |
| *Add the CI check* | Renders a workflow file into a repo (team buy-in for work repos) | `senior-coach install-ci --repo PATH` |
| *What does this senior-coach warning mean?* | Explains the finding and ties it to your open lesson | — |
| *Log a blast-radius note: …* | Stores a note hooks can look for | `senior-coach note --kind blast-radius --text "..."` |

Hooks start as **nudges** and can escalate. Never ask the agent to use `--no-verify` or edit `~/.senior-coach/state.json` to dodge a block.

---

## Verify and re-evaluate

| You say | What happens | CLI |
|---|---|---|
| *Verify my progress* / *Did I close the gap?* | Re-measures success signals from git/chat | `senior-coach verify` or `verify <gap>` |
| *Re-evaluate me* / *30/60/90 day check-in* | Same window as before; new scorecard + delta | collect → evaluate → `import` |
| *Show my history* / *Past verdicts* | Earlier evaluations from state | `senior-coach status` |

---

## Evidence and privacy

| You say | What happens |
|---|---|
| *Use these repos / this window / this chat export* | Confirms intake; re-runs collect if needed |
| *Don't install hooks* / *Skip CI* | Agent leaves hooks alone |
| *Where is my data?* | `~/.senior-coach/` (never inside the clone or your repos) |
| *Is this private?* | Local-only processing; reports may still contain paths/subjects — review before sharing |

---

## Uninstall / update

| You say | What happens |
|---|---|
| *Update the skill* | `git pull` in the clone; `init --relink` if you moved it |
| *Uninstall* / *Remove Senior Dev Coach* | Remove skill link, hooks, and `~/.senior-coach` (see `INSTALL.md`) |

---

## Phrases that do **not** work (and what to say instead)

| Avoid | Say instead |
|---|---|
| *Just mark everything done* | *I finished \<task\>; evidence is \<commit/PR\>* |
| *Ignore the hook / bypass the block* | Fix the finding, or accept a logged override only if you mean it |
| *Edit the skill folder for me* | Skill clone stays pristine; personalize via conversation + `~/.senior-coach` |
| *Score my teammate from their commits* | Skill only evaluates **your** work with your consent |

---

## Quick CLI cheat sheet

```text
senior-coach status          # where you are
senior-coach next            # next lesson / review
senior-coach report          # scorecard
senior-coach module <gap>    # one gap's tasks
senior-coach verify [gap]    # metric check
senior-coach --help          # full command list
```

Full install steps: [INSTALL.md](../INSTALL.md). Agent teaching rules: [SKILL.md](../SKILL.md).
