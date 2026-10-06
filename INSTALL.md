# Install Senior Dev Coach

About 5 minutes. Want your AI agent to do it for you? Use [AGENT_TAKE_THE_WHEEL.md](AGENT_TAKE_THE_WHEEL.md).

**You need:** `git`, Python 3.9+, and an agent that reads `SKILL.md` skills (Claude Code, Cursor 2.4+, Codex CLI, Gemini CLI). Optional: `gh` for PR-size metrics.

## Steps

1. **Clone it anywhere and leave it alone.** The clone is a template; never edit it. `git pull` updates it.
   ```bash
   git clone https://github.com/Remiiiiii/Senior-Dev-Coach ~/senior-dev-coach
   ```
2. **Inject it into your agent.** This links the skill into your agent's personal skills folder and creates a stable shim at `~/.senior-coach/bin/senior-coach`.
   ```bash
   python3 ~/senior-dev-coach/scripts/coach.py init        # auto-detects; or --agent claude-code|cursor|codex|gemini
   ```
   `init` prints the path to the **phrase book** (`references/phrase-book.md`) — what you can say to the agent (*what's next*, *status*, *verify*, …). Start a new agent session so it picks the skill up.
3. **Run the evaluation.** In your agent, say: *"Evaluate me as a developer."* It runs a read-only `discover` (repos, git identities, chat exports), then asks you to confirm the window (1, 4, 6 or 12 months), repos, identity and chat history, scores you, and saves the report.
4. **View the result.** Ask your agent, or run `~/.senior-coach/bin/senior-coach report`.
5. **Turn on live accountability, repo by repo, only if you want it.** Your agent will ask. Manual equivalents:
   ```bash
   senior-coach install-hooks --repo ~/code/app          # git hooks
   senior-coach integrate --agent claude-code            # agent hooks (or: --agent cursor --repo PATH)
   senior-coach install-ci --repo ~/code/app             # optional CI backstop (adds a file to the repo)
   ```
6. **Learn.** Say *"next lesson"* / *"what's next"* / *"next chapter"* to your agent (or `senior-coach next`). Full phrase list: [references/phrase-book.md](references/phrase-book.md). At about 30/60/90 days run `senior-coach verify` and re-evaluate with the same window.

**Update:** `git -C ~/senior-dev-coach pull`. **Moved the clone?** run `init --relink` from the new location. **Remove:** delete the `senior-dev-coach` link in your agent's skills folder, the hooks (`commit-msg`, `pre-commit`, `pre-push` in `.git/hooks`; restore any `*.pre-senior-coach` file), and `~/.senior-coach`.

## Recommendation

Start with **one repo**, a **6-month window** (4 if you have few commits), and **include chat history if you have it**. Stay in the default `nudge` mode: hooks only warn for the first 7 days, then escalate to blocking on overdue work. Read the full report before enabling hooks in any job repo.

## Gotchas

- **Claude Code:** personal skills don't load in Cowork or cloud sessions; run the agent locally. Restart after `init` if `~/.claude/skills` didn't exist before.
- **`--no-verify` skips git hooks.** The CI backstop catches secrets and oversized PRs.
- **Job repos:** husky or a tracked `core.hooksPath` is left untouched (it prints a line to add yourself). `install-ci` adds a file to the repo: ask your team first. Agent rules are kept out of git via `.git/info/exclude`.
- **Chat exports** from Claude.ai or ChatGPT are requested from the provider and arrive by email as a zip; the zip works as-is. Cursor chat is read straight from its local `state.vscdb` (no export needed; `discover` finds it). Chat is optional.
- **Under 10 commits in the window** means low-confidence scores.
- **Windows:** hooks are shell scripts; use Git Bash or WSL.
- **Privacy:** state lives in `~/.senior-coach` (never in your repos, never commit it). Reports contain commit subjects and file paths; review before sharing.
