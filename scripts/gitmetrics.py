#!/usr/bin/env python3
"""Collect engineering-habit metrics from git history over a window (1/4/6/12 months, or days).

Usage:
  gitmetrics.py --repo PATH_OR_GITHUB --months 6 [--me REGEX] [--agent REGEX] [--scan-secrets] [--prs]

Outputs JSON. Secrets are reported as {commit, file, kind} only, never the matched text.
"""
import argparse
import json
import os
import re
import statistics as st
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patterns as P  # noqa: E402

RS, US = "\x1e", "\x1f"
FMT = RS + US.join(["%H", "%an", "%ae", "%aI", "%P", "%s", "%b"]) + US


def run(cmd, cwd, check=False):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace")
    if check and r.returncode:
        raise RuntimeError(r.stderr.strip() or f"command failed: {' '.join(cmd)}")
    return r.stdout if r.returncode == 0 else ""


def window_since(months=None, days=None):
    d = days if days is not None else round((months or 6) * 30.4375)
    return datetime.now(timezone.utc) - timedelta(days=d)


def resolve_repo(spec, since, cache_dir):
    """Local path -> itself. 'owner/repo' or URL -> shallow clone into cache_dir."""
    p = Path(spec).expanduser()
    if p.exists():
        return p.resolve()
    url = spec
    if re.fullmatch(r"[\w.-]+/[\w.-]+", spec):
        url = f"https://github.com/{spec}.git"
    dest = Path(cache_dir) / re.sub(r"[^\w.-]+", "_", spec)
    if dest.exists():
        run(["git", "fetch", "--shallow-since=" + since.date().isoformat(), "origin"], dest)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--shallow-since=" + since.date().isoformat(), url, str(dest)],
                   check=True, capture_output=True, text=True)
    return dest


def _clean_path(p):
    # numstat rename forms: "a/{old => new}/b" or "old => new"
    m = re.match(r"^(.*)\{(.*) => (.*)\}(.*)$", p)
    if m:
        return re.sub(r"//+", "/", m.group(1) + m.group(3) + m.group(4))
    return p.split(" => ")[-1]


def parse_log(repo, since):
    out = run(["git", "log", "--since=" + since.isoformat(), "--numstat", "--date=iso-strict",
               "--format=" + FMT], repo)
    commits = []
    for chunk in out.split(RS):
        if not chunk.strip():
            continue
        parts = chunk.split(US)
        if len(parts) < 8:
            continue
        sha, an, ae, ad, parents, subj, body, numstat = parts[:8]
        files = []
        for line in numstat.strip().splitlines():
            m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", line)
            if m:
                a = 0 if m.group(1) == "-" else int(m.group(1))
                d = 0 if m.group(2) == "-" else int(m.group(2))
                files.append((_clean_path(m.group(3)), a, d))
        # Python 3.9's fromisoformat rejects the trailing Z that git --date=iso-strict emits.
        commits.append({"sha": sha, "author": f"{an} <{ae}>",
                        "ts": datetime.fromisoformat(ad.replace("Z", "+00:00")),
                        "merge": len(parents.split()) > 1, "subject": subj.strip(),
                        "body": body, "files": files})
    return commits


def classify(c, me_rx, agent_rx, bot_rx, solo):
    a = c["author"]
    if c["merge"]:
        return "merge"
    if bot_rx.search(a):
        return "bot"
    if agent_rx.search(a):
        return "agent"
    if me_rx.search(a) or solo:
        return "me"
    return "other"


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def _med(xs):
    return round(st.median(xs), 1) if xs else None


def _loc(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def largest_files(repo, god_loc, limit=10):
    names = run(["git", "ls-files", "-z"], repo).split("\0")[:20000]
    sized = []
    for n in names:
        if n and P.is_source(n):
            loc = _loc(Path(repo) / n)
            if loc:
                sized.append((loc, n))
    sized.sort(reverse=True)
    return [{"path": n, "loc": loc} for loc, n in sized[:limit]], sum(1 for loc, _ in sized if loc > god_loc)


def scan_secrets(repo, since):
    out = run(["git", "log", "-p", "-U0", "--no-merges", "--since=" + since.isoformat(),
               "--format=" + RS + "%H"], repo)
    hits, seen = [], set()
    for chunk in out.split(RS):
        lines = chunk.splitlines()
        if not lines:
            continue
        sha, cur = lines[0].strip(), None
        for ln in lines[1:]:
            if ln.startswith("+++ b/"):
                cur = ln[6:]
            elif ln.startswith("+") and not ln.startswith("+++"):
                k = P.secret_kind(ln)
                if k and (sha, cur, k) not in seen:
                    seen.add((sha, cur, k))
                    hits.append({"commit": sha[:10], "file": cur, "kind": k})
    return hits[:50]


def pr_metrics(repo, since):
    import shutil
    if not shutil.which("gh"):
        return {"available": False, "note": "gh CLI not installed; PR sizes skipped"}
    raw = run(["gh", "pr", "list", "--state", "all", "--limit", "200", "--search",
               f"created:>={since.date().isoformat()}", "--json",
               "number,title,additions,deletions,changedFiles,createdAt"], repo)
    try:
        prs = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return {"available": False, "note": "gh returned unparseable output"}
    sizes = [p["additions"] + p["deletions"] for p in prs]
    top = sorted(prs, key=lambda p: -(p["additions"] + p["deletions"]))[:5]
    return {"available": True, "count": len(prs), "median_lines": _med(sizes),
            "pr_over_1000_lines": sum(1 for s in sizes if s > 1000),
            "biggest": [{"number": p["number"], "title": p["title"][:80],
                         "lines": p["additions"] + p["deletions"], "files": p["changedFiles"]} for p in top]}


def metrics_for(commits, repo, opts):
    owned = [c for c in commits if c["cls"] in ("me", "agent") and not c["merge"]]
    fl = [[f for f in c["files"] if not P.is_noise(f[0])] for c in owned]
    nonempty = [(c, f) for c, f in zip(owned, fl) if f]
    files_per = [len(f) for _, f in nonempty]
    lines_per = [sum(a + d for _, a, d in f) for _, f in nonempty]
    subj = [c["subject"] for c in owned]
    conv = sum(1 for s in subj if P.CONVENTIONAL.match(s))
    vague = sum(1 for s in subj if not P.CONVENTIONAL.match(s) and (P.VAGUE_START.match(s) or len(s) < 15))
    risky_rx = re.compile(opts.get("risky_regex") or P.RISKY_DEFAULT, re.I)

    src = [(c, f) for c, f in nonempty if any(P.is_source(p) for p, _, _ in f)]
    with_tests = [x for x in src if any(P.is_test(p) for p, _, _ in x[1])]
    risky = [x for x in src if any(P.is_source(p) and risky_rx.search(p) for p, _, _ in x[1])]
    risky_untested = [x for x in risky if x not in with_tests]
    fixes = [x for x in src if P.FIX_SUBJECT.match(x[0]["subject"])]
    fixes_untested = [x for x in fixes if x not in with_tests]

    # fix-after-ship: a fix commit touching a file another non-fix owned commit touched <=72h earlier
    last, followups = {}, 0
    for c, f in sorted(nonempty, key=lambda x: x[0]["ts"]):
        is_fix = bool(P.FIX_SUBJECT.match(c["subject"]))
        if is_fix and any(p in last and c["ts"] - last[p] <= timedelta(hours=72) for p, _, _ in f):
            followups += 1
        if not is_fix:
            for p, _, _ in f:
                last[p] = c["ts"]

    churn = Counter(p for _, f in nonempty for p, _, _ in f if P.is_code(p))
    god_loc = opts.get("god_file_loc", 800)
    hot = []
    for p, n in churn.most_common(15):
        hot.append({"path": p, "touches": n, "loc": _loc(Path(repo) / p)})
    big, god_count = largest_files(repo, god_loc)
    largest = sorted(nonempty, key=lambda x: -len(x[1]))[:3]
    all_touches = sum(len(f) for _, f in nonempty)
    test_touches = sum(1 for _, f in nonempty for p, _, _ in f if P.is_test(p))
    monthly = Counter(c["ts"].strftime("%Y-%m") for c in owned)
    n_own = len(owned)
    ai_asst = sum(1 for c in owned if c["cls"] == "agent" or P.AI_COAUTHOR.search(c["body"]))
    m = {
        "commits_owned": n_own,
        "commits_me": sum(1 for c in commits if c["cls"] == "me"),
        "commits_agent": sum(1 for c in commits if c["cls"] == "agent"),
        "commits_merge": sum(1 for c in commits if c["cls"] == "merge"),
        "commits_other_authors": sum(1 for c in commits if c["cls"] == "other"),
        "agent_share_pct": _pct(sum(1 for c in owned if c["cls"] == "agent"), n_own),
        "ai_assisted_pct": _pct(ai_asst, n_own),
        "lines_added": sum(a for _, f in nonempty for _, a, _ in f),
        "lines_deleted": sum(d for _, f in nonempty for _, _, d in f),
        "median_files_per_commit": _med(files_per),
        "p90_files_per_commit": (sorted(files_per)[int(0.9 * (len(files_per) - 1))] if files_per else None),
        "large_commit_pct": _pct(sum(1 for x in files_per if x > 40), len(files_per)),
        "median_lines_per_commit": _med(lines_per),
        "conventional_pct": _pct(conv, n_own),
        "vague_message_pct": _pct(vague, n_own),
        "source_commits": len(src),
        "test_colocation_pct": _pct(len(with_tests), len(src)),
        "test_path_touch_pct": _pct(test_touches, all_touches),
        "risky_commits": len(risky),
        "risky_without_test_pct": _pct(len(risky_untested), len(risky)),
        "fix_commits": len(fixes),
        "fix_without_test_pct": _pct(len(fixes_untested), len(fixes)),
        "fix_after_ship_pct": _pct(followups, n_own),
        "revert_count": sum(1 for s in subj if s.lower().startswith("revert")),
        "god_file_loc_threshold": god_loc,
        "god_file_count": god_count,
        "god_hotspot_count": sum(1 for h in hot if (h["loc"] or 0) > god_loc),
        "hotspots": hot,
        "largest_files": big,
        "largest_commits": [{"sha": c["sha"][:10], "files": len(f), "subject": c["subject"][:80]}
                            for c, f in largest],
        "commits_per_month": dict(sorted(monthly.items())),
    }
    return m


def collect(repos, since, me=None, agent=None, scan=False, prs=False, opts=None, cache_dir=None):
    opts = opts or {}
    cache_dir = cache_dir or Path.home() / ".senior-coach" / "cache"
    agent_rx = re.compile("|".join(agent) if agent else P.AGENT_AUTHOR_DEFAULT, re.I)
    bot_rx = re.compile(P.BOT_AUTHOR_DEFAULT, re.I)
    result = {"window": {"since": since.date().isoformat(),
                         "until": datetime.now(timezone.utc).date().isoformat()},
              "repos": {}, "notes": []}
    union = []
    for spec in repos:
        try:
            path = resolve_repo(spec, since, cache_dir)
        except Exception as e:  # noqa: BLE001
            result["notes"].append(f"{spec}: could not open ({e})")
            continue
        solo = not me
        if solo:
            cfg = run(["git", "config", "user.email"], path).strip()
            if cfg:
                me_rx, solo = re.compile(re.escape(cfg), re.I), False
                result["notes"].append(f"{path.name}: --me not given; using git config user.email")
            else:
                me_rx = re.compile("$^")
                result["notes"].append(f"{path.name}: --me not given and no user.email; "
                                       "treating every non-agent author as you (solo assumed)")
        else:
            me_rx = re.compile("|".join(me), re.I)
        commits = parse_log(path, since)
        for c in commits:
            c["cls"] = classify(c, me_rx, agent_rx, bot_rx, solo)
        m = metrics_for(commits, path, opts)
        if scan:
            m["secret_signals"] = scan_secrets(path, since)
            m["secret_signal_count"] = len(m["secret_signals"])
        if prs:
            m["prs"] = pr_metrics(path, since)
        result["repos"][path.name] = m
        for c in commits:
            c["repo"] = path.name
        union.extend(commits)
    if len(result["repos"]) == 1:
        result["combined"] = next(iter(result["repos"].values()))
    elif result["repos"]:
        # recompute habit metrics on the union; hotspots stay per repo
        first = next(iter(result["repos"]))
        comb = metrics_for(union, Path(repos[0]).expanduser(), opts)
        comb.pop("hotspots", None), comb.pop("largest_files", None)
        comb["secret_signal_count"] = sum(r.get("secret_signal_count", 0) for r in result["repos"].values())
        comb["note"] = f"habit metrics recomputed over {len(result['repos'])} repos; hotspots per repo (first: {first})"
        result["combined"] = comb
    if not result["repos"]:
        result["notes"].append("no repositories could be analyzed")
    elif result["combined"]["commits_owned"] < 10:
        result["notes"].append("fewer than 10 owned commits in window: treat all git-based scores as low confidence")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", required=True)
    ap.add_argument("--months", type=float, default=6)
    ap.add_argument("--days", type=int)
    ap.add_argument("--me", action="append", help="regex matching 'Name <email>' of YOU (repeatable)")
    ap.add_argument("--agent", action="append", help="regex for AI-agent authors (repeatable)")
    ap.add_argument("--scan-secrets", action="store_true")
    ap.add_argument("--prs", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    res = collect(a.repo, window_since(a.months, a.days), a.me, a.agent, a.scan_secrets, a.prs)
    txt = json.dumps(res, indent=2, default=str)
    Path(a.out).write_text(txt) if a.out else print(txt)


if __name__ == "__main__":
    main()
