# Integrations

All of these call `coach.py check` through the stable shim `~/.senior-coach/bin/senior-coach` (created by `init`), so moving the clone doesn't break them (`init --relink`). They stay silent until you have imported a plan. Prefer the commands below over hand-copying the snippets here; the snippets are references.

## 1. Git hooks (recommended)
```bash
senior-coach install-hooks --repo /path/to/your/repo
```
Installs `commit-msg`, `pre-commit`, `pre-push`. Existing hooks are preserved (renamed `*.pre-senior-coach` and chained). Husky or a tracked `core.hooksPath` is left untouched. If the shim is removed the hooks exit quietly rather than breaking commits. Bypass is `--no-verify`, which is why you also want #4.

## 2. Claude Code
```bash
senior-coach integrate --agent claude-code        # merges into ~/.claude/settings.json (backs it up once; idempotent; --dry-run to preview)
```
Adds a `UserPromptSubmit` hook (prompt-contract nudge; its stdout is injected as context for Claude) and a `Stop` hook (`agent-done` checks; exit code 2 blocks stopping so Claude fixes the finding first). The script exits quietly when `stop_hook_active` is set, and blocks at most once per identical diff because `stop_hook_active` has been reported unreliable in some versions. `claude-code-settings.json` is the reference shape.

## 3. Cursor / Codex / other agents
```bash
senior-coach integrate --agent cursor --repo PATH      # writes .cursor/rules/senior-coach.mdc, kept out of git via .git/info/exclude
senior-coach integrate --agent agents-md --repo PATH   # writes AGENTS.md only if absent; never edits an existing one
```
Rules are advisory; the git hooks are what enforce, and they apply to commits made by any agent.

## 4. GitHub Action backstop
`senior-coach install-ci --repo PATH` writes `.github/workflows/senior-coach.yml` (owner resolved from the clone's origin; it adds a file to the repo, so get team buy-in for job repos). It runs stateless (all library gaps active, defaults): fails on secrets in the PR range, warns on oversized PRs.
