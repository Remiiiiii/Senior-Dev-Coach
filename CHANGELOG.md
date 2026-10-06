# Changelog

Format: [Keep a Changelog](https://keepachangelog.com), versioning: [SemVer](https://semver.org).

## [Unreleased]
### Added
- User phrase book (`references/phrase-book.md`); `init` prints its path and INSTALL/SKILL point to it.
- Cursor chat history support (`state.vscdb`, `agent-transcripts`).
- Integrity guard (`.github/scripts/guard.py`) run from the base branch on every pull request.
- CI, CodeQL, dependency review; pinned actions; Dependabot; CODEOWNERS; importable rulesets.
- `SECURITY.md` threat model, `CONTRIBUTING.md`, issue and PR templates.
### Changed
- CI template runs with read-only permissions and pins the coach to a release tag.
