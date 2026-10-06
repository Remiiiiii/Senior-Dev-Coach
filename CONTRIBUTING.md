# Contributing

Thanks for helping. This project is small on purpose: **zero runtime dependencies, no network access, local-only data.**

## Setup

```bash
git clone https://github.com/Remiiiiii/Senior-Dev-Coach && cd Senior-Dev-Coach
python3 -m unittest discover -s tests          # Python 3.9+
python3 -I .github/scripts/guard.py            # same integrity checks CI runs
```

## Rules of the road

- Open an issue first for anything larger than a bug fix.
- One logical change per pull request, with tests. Keep functions small and typed where it helps.
- **Do not add** dependencies, network calls, `eval`/`exec`, `shell=True`, downloaded code, or text that instructs the agent to hide actions from the user, skip checks or read credentials. `guard` blocks these and a human will too.
- Changes to `SKILL.md`, `scripts/`, `integrations/`, `prompts/`, `references/` or `.github/` get extra scrutiny from code owners; explain the security impact in the PR.
- Sign your commits. Use [Conventional Commits](https://www.conventionalcommits.org) (`fix:`, `feat:`, `docs:`, `ci:`).
- If `guard` flags a false positive, add a narrowly scoped entry with a `reason` to `.github/guard-allowlist.json`. Never loosen the rules in a feature PR.

Adding a gap, rule or parser: use `prompts/extend.md`. Security issues: see [SECURITY.md](SECURITY.md). Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
