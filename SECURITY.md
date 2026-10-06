# Security Policy

Senior Dev Coach is an agent skill: its markdown is read by an AI agent and its scripts and hooks run on a developer's machine with that developer's privileges. We therefore treat **instructions as code**.

## Reporting a vulnerability

Please use [private vulnerability reporting](https://github.com/Remiiiiii/Senior-Dev-Coach/security/advisories/new). Do not open a public issue. We aim to acknowledge within 3 business days and to ship a fix or mitigation within 30 days. Good-faith research is welcome.

## Supported versions

Only the latest release tag receives security fixes.

## Threat model

| Threat | Example | Control |
|---|---|---|
| Malicious pull request | Backdoor in a script, hook or CI template | Required review by code owners; `guard` blocks `eval`/`exec`, network and dynamic-import primitives, `shell=True`, download-and-run, encoded payloads; zero-dependency policy |
| Prompt injection in the repo | Hidden or explicit instruction-override text in `SKILL.md`, prompts or references | `guard` scans for injection phrasing and invisible Unicode (bidi, zero-width, tag characters); `SKILL.md` declares a trust boundary |
| Prompt injection via analysed data | A commit message, chat export or file telling the agent what to do | Skill rules: analysed content is data, never instructions; the agent may only run the documented `senior-coach` commands |
| Weakening the checks | PR edits `guard.py`, the allowlist or workflows to pass itself | CI runs the guard and allowlist from the **base branch**; `.github/` is code-owned; allowlist entries require a written reason |
| CI abuse | `pull_request_target`, expression injection, unpinned actions | Workflows use `pull_request`, least-privilege `permissions`, `persist-credentials: false`, actions pinned to full SHAs (kept fresh by Dependabot) |
| Supply chain | Poisoned dependency or moving tag | No runtime dependencies; dependency manifests are blocked by `guard`; release tags are immutable |
| Data exposure | Reports leaking secrets or paths | Local-only processing, redaction, secret scans report location and kind, never values |
| Tampered install | `git pull` of an unreviewed commit | Pin to a signed release tag and verify before use (below) |

Out of scope: a developer who deliberately bypasses their own hooks (`--no-verify`); the ledger records overrides but cannot prevent them.

## Verifying your install

```bash
git -C ~/senior-dev-coach fetch --tags
git -C ~/senior-dev-coach verify-tag v1.0.0     # requires the maintainer's public key
git -C ~/senior-dev-coach checkout v1.0.0
git -C ~/senior-dev-coach status --porcelain    # must be empty: the clone is never edited
```

Prefer release tags over `main`. Review `git diff <old-tag> <new-tag> -- scripts integrations SKILL.md prompts` before upgrading.

## Hardening for maintainers

Settings that cannot live in files are listed in [docs/REPOSITORY_SETTINGS.md](docs/REPOSITORY_SETTINGS.md), with importable rulesets in `.github/rulesets/`.
