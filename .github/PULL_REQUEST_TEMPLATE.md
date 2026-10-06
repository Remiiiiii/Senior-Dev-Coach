## Summary
<!-- What changes and why. Link the issue. -->

## Type
- [ ] Fix  - [ ] Feature  - [ ] Docs  - [ ] Refactor  - [ ] CI / security

## Checklist
- [ ] `python3 -m unittest discover -s tests` passes locally
- [ ] `python3 -I .github/scripts/guard.py` passes locally
- [ ] No new dependencies, network calls, `eval`/`exec`, `shell=True` or downloaded code
- [ ] No instructions aimed at the agent or user were added to docs, prompts or references that change what the skill is allowed to do
- [ ] Commits are signed
- [ ] Touches `SKILL.md`, `scripts/`, `integrations/`, `prompts/`, `references/` or `.github/`? Explain the security impact below.

## Security impact
<!-- "None" is a valid answer for docs-only changes. Otherwise describe trust-boundary, data-flow or permission changes. -->
