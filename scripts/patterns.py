"""Shared patterns. Heuristics, not truth: every consumer treats hits as signals to investigate."""
import re

CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: \S.{2,}")
VAGUE_START = re.compile(
    r"^(enhance|refactor|update|updates|improve|improvements?|change|changes|wip|misc|cleanup|"
    r"clean up|tweak|tweaks|minor|fixes|fix|stuff|more|small)\b", re.I)
FIX_SUBJECT = re.compile(r"^(fix|hotfix|bugfix|bug)\b|^\w+(\([^)]*\))?!?:\s*(fix|hotfix)", re.I)

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|specs?|e2e|cypress|playwright)(/|$)"
    r"|\.(test|spec)\.[A-Za-z0-9]+$|_test\.(go|py|rb)$|(^|/)test_[^/]+\.py$")
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rs", ".java", ".kt", ".rb",
            ".php", ".cs", ".swift", ".dart", ".vue", ".svelte", ".scala", ".c", ".cc", ".cpp", ".h"}
NOISE = re.compile(
    r"(^|/)(node_modules|dist|build|\.next|vendor|coverage|__snapshots__)/"
    r"|(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|poetry\.lock|Gemfile\.lock|go\.sum)$"
    r"|\.(min\.js|map|snap|lock)$")
RISKY_DEFAULT = (r"rbac|auth(?!or)|permission|payment|billing|stripe|tenant|secret|session|"
                 r"(^|/)acl|(^|/)orgs?(/|\.|_)|organization")

AI_COAUTHOR = re.compile(r"co-authored-by:.*(claude|copilot|cursor|codex|gemini|aider|devin)", re.I)
AGENT_AUTHOR_DEFAULT = r"cursor ?agent|cursoragent|claude|copilot|devin|codex|aider|openhands|gemini"
BOT_AUTHOR_DEFAULT = r"\[bot\]|dependabot|renovate|github-actions"

PLACEHOLDER = re.compile(r"process\.env|example|your[_-]|xxx|changeme|placeholder|<[^>]+>|\$\{", re.I)
SECRET_PATTERNS = [
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe-live-key", re.compile(r"sk_live_[0-9a-zA-Z]{16,}")),
    ("private-key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("generic-credential", re.compile(
        r"(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]", re.I)),
]


def secret_kind(line: str):
    """Return the kind of secret a line looks like, or None. Never returns the secret itself."""
    for kind, rx in SECRET_PATTERNS:
        if rx.search(line) and not (kind == "generic-credential" and PLACEHOLDER.search(line)):
            return kind
    return None


def is_test(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def is_noise(path: str) -> bool:
    return bool(NOISE.search(path))


def is_source(path: str) -> bool:
    ext = "." + path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    return ext in CODE_EXT and not is_test(path) and not is_noise(path)


def is_code(path: str) -> bool:
    ext = "." + path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    return ext in CODE_EXT and not is_noise(path)
