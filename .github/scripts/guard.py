#!/usr/bin/env python3
"""Repository integrity guard (stdlib only, never imports or executes scanned code).

Runs in CI from the BASE branch against the PR checkout, so a pull request cannot weaken
the rules that judge it. Exit 1 on any non-allowlisted error finding.

Rules
  unicode      bidi / zero-width / tag characters (Trojan Source, invisible prompt injection)
  injection    prompt-injection phrasing inside skill, prompt and reference files
  code         eval/exec, os.system, shell=True, pickle, network and dynamic-import primitives (AST)
  shell        download-and-run, encoded payloads, reverse shells in scripts, hooks and templates
  workflow     pull_request_target, unpinned actions, missing permissions, expression injection
  filetype     symlinks, executables, binaries, oversized files, dependency manifests, odd filenames
  secret       high-signal credential formats
  sensitive    (notice) change touches a security-sensitive path: needs code-owner review
"""
import argparse, ast, json, os, re, subprocess, sys
from pathlib import Path

SENSITIVE = ("SKILL.md", "scripts/", "integrations/", "prompts/", "references/", ".github/", "evals/")
TEXT_EXT = {".py", ".md", ".json", ".yml", ".yaml", ".txt", ".sh", ".toml", ".cfg", ".ini", ""}
MAX_BYTES = 512 * 1024
MANIFESTS = {"requirements.txt", "package.json", "package-lock.json", "pyproject.toml", "setup.py", "setup.cfg",
             "pipfile", "pipfile.lock", "poetry.lock", "yarn.lock", "dockerfile", "makefile", ".gitmodules",
             ".npmrc", ".pypirc", "sitecustomize.py", "usercustomize.py", "conftest.py", "tox.ini"}
BAD_IMPORTS = {"socket", "urllib", "urllib2", "urllib3", "http", "requests", "httpx", "aiohttp", "ftplib",
               "smtplib", "telnetlib", "xmlrpc", "paramiko", "webbrowser", "ctypes", "pickle", "marshal",
               "shelve", "pty", "code", "importlib", "imp", "pip", "ensurepip"}
BAD_NAME_CALLS = {"eval", "exec", "compile", "__import__"}
BAD_ATTR_CALLS = {"system", "popen", "spawnl", "spawnv", "execv", "execl", "startfile", "run_module", "run_path",
                  "b64decode", "urlopen"}

UNICODE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")
INJECTION = [re.compile(p, re.I) for p in (
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|guidelines|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above|earlier|your) ",
    r"(do not|don't|never) (tell|inform|mention|show|reveal)[^.\n]{0,40}\b(the )?user",
    r"without (telling|informing|notifying|asking) (the )?(user|developer)",
    r"you are now (a|an|in) ", r"new (system )?instructions?:", r"</?(system|assistant|developer)>",
    r"(send|post|upload|exfiltrate|forward)[^.\n]{0,50}(token|secret|credential|api[ _-]?key|ssh|\.env|password)",
    r"(read|cat|print|dump)[^.\n]{0,30}(~/\.ssh|\.aws/credentials|id_rsa|\.netrc|keychain)",
    r"(auto|silently)[ -]?(approve|accept|merge|run)", r"bypass (the )?(hook|check|review|guard|sandbox)",
)]
SHELL = [re.compile(p, re.I) for p in (
    r"\b(curl|wget|iwr|invoke-webrequest|invoke-expression|nc|ncat|netcat|socat)\b\s",
    r"\|\s*(ba|z|da)?sh\b", r"/dev/(tcp|udp)/", r"base64\s+(-d|--decode)", r"\beval\s+[\"'$(]",
    r"\b(bash|sh|powershell|pwsh|cmd)\s+-(c|command|enc)\b", r"chmod\s+\+?[ugoa]*\+?x", r"\bcrontab\b|\blaunchctl\b|\bschtasks\b",
    r"\b(pip|pip3|npm|npx|yarn|pnpm|gem|cargo)\s+(install|i|add)\b", r"\bsudo\b",
)]
SECRET = [(k, re.compile(p)) for k, p in (
    ("aws-key", r"\bAKIA[0-9A-Z]{16}\b"), ("github-token", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    ("private-key", r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    ("slack-token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), ("anthropic-key", r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ("openai-key", r"\bsk-[A-Za-z0-9]{32,}\b"), ("google-key", r"\bAIza[0-9A-Za-z_-]{35}\b"))]
SHA = re.compile(r"@[0-9a-f]{40}\b")
CONTENT_EXEMPT = {".github/scripts/guard.py", ".github/guard-allowlist.json", "tests/test_guard.py"}


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def scan_text(rel, text, add):
    ext = Path(rel).suffix.lower()
    if rel not in CONTENT_EXEMPT:
        for m in UNICODE.finditer(text):
            if m.group() == "\ufeff" and m.start() == 0:
                continue
            add("unicode", rel, line_of(text, m.start()), f"hidden character U+{ord(m.group()):04X}")
        for i, ln in enumerate(text.splitlines(), 1):
            for p in INJECTION:
                if p.search(ln):
                    add("injection", rel, i, f"prompt-injection phrasing: {p.pattern[:48]}")
            for k, p in SECRET:
                if p.search(ln):
                    add("secret", rel, i, f"possible {k}")
            if ext in {".sh", ".yml", ".yaml", ".json", ".md", ""} or rel.startswith(("integrations/", ".github/")):
                for p in SHELL:
                    if p.search(ln) and not (ext == ".md" and not rel.startswith("integrations/")):
                        add("shell", rel, i, f"risky shell pattern: {p.pattern[:48]}")
    if ext == ".py":
        scan_python(rel, text, add)
    if rel.startswith(".github/workflows/") or rel.startswith("integrations/") and ext in {".yml", ".yaml"}:
        scan_workflow(rel, text, add)


def scan_python(rel, text, add):
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return add("code", rel, e.lineno or 1, "syntax error: file cannot be parsed")
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in BAD_IMPORTS:
                    add("code", rel, n.lineno, f"import {a.name}")
        elif isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in BAD_IMPORTS:
            add("code", rel, n.lineno, f"from {n.module} import ...")
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) and f.id in BAD_NAME_CALLS else \
                f.attr if isinstance(f, ast.Attribute) and f.attr in BAD_ATTR_CALLS else ""
            if name:
                add("code", rel, n.lineno, f"call to {name}()")
            for kw in n.keywords:
                if kw.arg == "shell" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                    add("code", rel, n.lineno, "shell=True")


def scan_workflow(rel, text, add):
    if re.search(r"\bpull_request_target\b|\bworkflow_run\b|runs-on:.*self-hosted|secrets:\s*inherit", text):
        add("workflow", rel, 1, "pull_request_target / workflow_run / self-hosted / secrets: inherit are not allowed")
    if rel.startswith(".github/workflows/") and not re.search(r"^permissions:", text, re.M):
        add("workflow", rel, 1, "missing top-level `permissions:` (default must be least privilege)")
    for i, ln in enumerate(text.splitlines(), 1):
        m = re.search(r"uses:\s*([^\s#]+)", ln)
        if m and not m.group(1).startswith("./") and not SHA.search(m.group(1)):
            add("workflow", rel, i, f"action not pinned to a full commit SHA: {m.group(1)}")
        if re.search(r"\$\{\{\s*(github\.(event\.|head_ref)|inputs\.)", ln) and "run" in ln:
            add("workflow", rel, i, "untrusted expression interpolated into a shell command")
    for blk in re.finditer(r"run:\s*[|>][^\n]*\n((?:[ \t]+.*\n?)+)", text):
        for j, ln in enumerate(blk.group(1).splitlines()):
            if re.search(r"\$\{\{\s*(github\.(event\.|head_ref)|inputs\.)", ln):
                add("workflow", rel, line_of(text, blk.start()) + j + 1, "untrusted expression in run block")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="checkout to scan (the PR head)")
    ap.add_argument("--base", help="base commit/ref: scan only changed files and flag sensitive paths")
    ap.add_argument("--allowlist", help="allowlist JSON (use the BASE branch copy in CI)")
    a = ap.parse_args()
    root = Path(a.repo).resolve()
    findings, notices = [], []

    def add(rule, path, line, msg):
        findings.append({"rule": rule, "path": path, "line": line, "message": msg})

    ls = git(root, "ls-files", "-s", "-z").split("\0")
    entries = {}
    for e in filter(None, ls):
        meta, path = e.split("\t", 1)
        entries[path] = meta.split()[0]
    paths = sorted(entries)
    if a.base:
        changed = set(git(root, "diff", "--name-only", "-z", "--diff-filter=ACMRT", f"{a.base}...HEAD").split("\0")) - {""}
        paths = [p for p in paths if p in changed]
        for p in sorted(changed):
            if p.startswith(SENSITIVE) or p in SENSITIVE:
                notices.append(p)
    for rel in paths:
        mode = entries[rel]
        name = Path(rel).name
        if mode == "120000":
            add("filetype", rel, 1, "symlink")
            continue
        if mode == "160000":
            add("filetype", rel, 1, "submodule")
            continue
        if not rel.isascii() or re.search(r"[\s\\]|(^|/)\.\.?(/|$)|^-", rel):
            add("filetype", rel, 1, "non-ASCII, whitespace or traversal-like filename")
        if mode == "100755" and not rel.endswith(".py"):
            add("filetype", rel, 1, "executable bit set")
        if name.lower() in MANIFESTS or name.lower().startswith((".env", "requirements")) or name.endswith((".pth", ".whl", ".egg")):
            add("filetype", rel, 1, "dependency/build manifest: this project is zero-dependency; maintainer review required")
        p = root / rel
        if not p.is_file():
            continue
        data = p.read_bytes()
        if len(data) > MAX_BYTES:
            add("filetype", rel, 1, f"file larger than {MAX_BYTES // 1024} KB")
        if b"\0" in data:
            add("filetype", rel, 1, "binary file")
            continue
        if Path(rel).suffix.lower() in TEXT_EXT or rel.startswith(".github/"):
            try:
                scan_text(rel, data.decode("utf-8"), add)
            except UnicodeDecodeError:
                add("filetype", rel, 1, "not valid UTF-8")
    allow = []
    if a.allowlist and Path(a.allowlist).is_file():
        allow = json.loads(Path(a.allowlist).read_text())
        for r in allow:
            if not r.get("reason"):
                sys.exit("allowlist entries need a `reason`")

    def allowed(f):
        return any(r["rule"] == f["rule"] and r["path"] == f["path"] and
                   (not r.get("contains") or r["contains"] in f["message"]) for r in allow)

    bad = [f for f in findings if not allowed(f)]
    for f in bad:
        print(f"::error file={f['path']},line={f['line']},title=guard/{f['rule']}::{f['message']}")
    for p in notices:
        print(f"::notice file={p},title=guard/sensitive::security-sensitive path changed; code-owner review required")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(f"### Integrity guard\n\n**{len(bad)}** blocking finding(s), {len(findings) - len(bad)} allowlisted, "
                     f"{len(notices)} sensitive path(s) changed.\n\n")
            for f in bad:
                fh.write(f"- `{f['path']}:{f['line']}` **{f['rule']}**: {f['message']}\n")
            for p in notices:
                fh.write(f"- :lock: sensitive: `{p}`\n")
    print(f"guard: {len(paths)} files scanned, {len(bad)} blocking, {len(findings) - len(bad)} allowlisted, {len(notices)} sensitive")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
