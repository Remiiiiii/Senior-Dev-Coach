# Repository settings checklist

Do these once after pushing. Files in the repo cannot enforce them.

1. **Rulesets** (Settings > Rules > Rulesets > Import): `.github/rulesets/main.json` and `.github/rulesets/tags.json`. They require signed commits, linear history, code-owner approval, fresh approval after the last push, resolved threads and the status checks `guard`, `test (3.9|3.12|3.13)`, `dependency-review`, `codeql (python|actions)`. The admin role can bypass only through a pull request.
2. **Actions** (Settings > Actions > General): allow GitHub-owned actions only; default `GITHUB_TOKEN` to read-only; require approval for all outside collaborators; disable "Allow GitHub Actions to create and approve pull requests".
3. **Code security**: enable Dependency graph, Dependabot alerts and security updates, secret scanning with push protection, private vulnerability reporting.
4. **Account**: two-factor authentication with a hardware key or passkey; sign commits and tags (SSH or GPG).
5. **Releases**: create annotated, signed tags (`git tag -s v1.0.0 -m "v1.0.0"`). The CI template in `integrations/github-action.yml` and `SECURITY.md` pin to them.
6. **Second maintainer**: with one maintainer, "require approval" blocks your own PRs unless you use the admin bypass. Add a second code owner when you can.

The first commit that introduces `guard.py` must be pushed directly to `main`; afterwards every change goes through a pull request.
