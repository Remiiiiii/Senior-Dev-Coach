---
description: Senior-coach accountability for AI-assisted work
alwaysApply: true
---
The developer follows a senior-dev-coach plan (state in ~/.senior-coach). While working:

1. Before starting a non-trivial task, if the developer's request lacks constraints/non-goals, allowed files, or required tests, ask for them (or state your assumptions and get a yes). Optional check: `{{SHIM}} check --event prompt --audience agent --out stdout --text "<their request>"`.
2. Before saying work is finished, run `{{SHIM}} check --event agent-done --audience agent --out stdout`. Follow every `agent instruction:` line. Tell the developer which plan task each finding relates to.
3. For a large change (many files or lines), ask the developer for a 5-bullet blast-radius note (callers, auth, data, UI, rollback) and log it: `{{SHIM}} note --kind blast-radius --text "..."`.
4. Never bypass a block: no `--no-verify`, no editing hooks or the state file, no marking tasks done for the developer. If they choose to override, they set `COACH_OVERRIDE` themselves.
5. Keep scope tight: touch only the files the task needs; propose a split instead of expanding.
