#!/usr/bin/env python3
"""senior-dev-coach CLI: evidence collection, plan state, module progress, live-dev accountability.

  coach.py collect --months 6 --repo PATH --chat PATH [--me REGEX]   # evidence for the evaluation
  coach.py suggest-gaps [--evidence FILE]                              # detector cross-check
  coach.py discover [--root DIR]                                       # find repos, git identity, chat exports, agents
  coach.py init [--agent claude-code|cursor|codex|gemini|agents]       # inject the skill into your agent (symlink + shim)
  coach.py import evaluation.json [--report FILE] [--mode ...]         # evaluation -> plan + task state
  coach.py report [--save FILE]                                        # view the latest evaluation
  coach.py module GAP | status | next | task GAP TASK start|done      # LMS loop
  coach.py verify [GAP] [--chat PATH]                                  # auto-verify signals/metric tasks
  coach.py check --event commit-msg|pre-commit|pre-push|agent-done|prompt|ci   # accountability (hooks call this)
  coach.py note --kind blast-radius --text "..."                       # log a note the checks look for
  coach.py install-hooks [--repo .] | integrate --agent claude-code|cursor|agents-md | install-ci [--repo .]
  coach.py set-owner NAME        # maintainer-only, once, before first push | ledger [-n 20]

State lives in $SENIOR_COACH_HOME (default ~/.senior-coach), never inside your repos.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import chatmetrics as C  # noqa: E402
import gitmetrics as G  # noqa: E402
import patterns as P  # noqa: E402

LIB = json.loads((ROOT / "references" / "gap-library.json").read_text())
HOME = Path(os.environ.get("SENIOR_COACH_HOME") or Path.home() / ".senior-coach")
STATE = HOME / "state.json"
DEFAULTS = {"mode": "nudge", "auto_escalate": True, "commit_file_cap": 15, "pr_line_cap": 800, "pr_file_cap": 40,
            "god_file_loc": 800, "risky_regex": P.RISKY_DEFAULT}
OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b,
       "<=": lambda a, b: a <= b, "==": lambda a, b: a == b}
NOW = lambda: datetime.now(timezone.utc)  # noqa: E731
TODAY = lambda: NOW().date()  # noqa: E731


# ---------- state ----------
def load(required=True):
    if STATE.exists():
        return json.loads(STATE.read_text())
    if required:
        sys.exit(f"No plan yet ({STATE} missing). Run: collect -> evaluate -> import.")
    return None


def save(s):
    HOME.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2, default=str))


def log(s, **ev):
    s.setdefault("ledger", []).append({"ts": NOW().isoformat(timespec="seconds"), **ev})
    s["ledger"] = s["ledger"][-2000:]


def ago(ts, **kw):
    return datetime.fromisoformat(ts) >= NOW() - timedelta(**kw)


def git(args, cwd=None):
    return G.run(["git"] + args, cwd or os.getcwd())


# ---------- collect / suggest ----------
def latest_evidence(path=None):
    if path:
        return json.loads(Path(path).read_text())
    files = sorted((HOME / "evidence").glob("evidence-*.json")) if (HOME / "evidence").exists() else []
    if not files:
        sys.exit("No evidence file. Run `coach.py collect` first.")
    return json.loads(files[-1].read_text())


def get_metric(name, ev=None, chat=None, state=None, since=None):
    ns, _, key = name.partition(".")
    if ns == "git":
        return ((ev or {}).get("git") or {}).get("combined", {}).get(key)
    if ns == "chat":
        c = chat if chat is not None else (ev or {}).get("chat")
        return c.get(key) if c and c.get("available") else None
    if ns == "ledger":
        s0 = (state or {}).get("plan", {}).get("start", "1970-01-01")
        return sum(1 for e in (state or {}).get("ledger", [])
                   if e.get("type") == "note" and e.get("kind") == "blast-radius" and e["ts"][:10] >= s0)
    if ns == "env":
        return env_metric(key, state)
    if ns == "plan" and key == "top_hotspot_loc_reduction_pct":
        return hotspot_reduction(state)
    return None


def env_metric(key, state):
    repos = [Path(r).expanduser() for r in (state or {}).get("settings", {}).get("repos", []) if Path(r).expanduser().exists()]
    if key == "hooks_installed":
        for r in repos:
            hp = Path(git(["rev-parse", "--git-path", "hooks"], r).strip() or ".git/hooks")
            hp = hp if hp.is_absolute() else r / hp
            if any("senior-coach" in f.read_text(errors="ignore") for f in hp.glob("*") if f.is_file() and not f.name.endswith(".sample")):
                return 1
        return 0
    if key == "pr_template":
        return int(any((r / ".github" / n).exists() for r in repos for n in ("pull_request_template.md", "PULL_REQUEST_TEMPLATE.md")))
    return None


def hotspot_reduction(state):
    gods = (state or {}).get("plan", {}).get("context", {}).get("god_files", [])[:3]
    if not gods:
        return None
    red = []
    for g in gods:
        cur = G._loc(g["abs"]) if Path(g["abs"]).exists() else 0
        red.append(max(0.0, 100.0 * (g["loc"] - (cur or 0)) / g["loc"]))
    return round(sum(red) / len(red), 1)


def cmd_collect(a):
    since = G.window_since(a.months, a.days)
    opts = {"risky_regex": a.risky_regex, "god_file_loc": a.god_loc}
    git_ev = G.collect(a.repo, since, a.me, a.agent, a.scan_secrets, a.prs, opts, HOME / "cache")
    chat = C.collect(a.chat, since) if a.chat else None
    ev = {"collected": NOW().isoformat(timespec="seconds"),
          "window": {"since": since.date().isoformat(), "until": TODAY().isoformat(), "months": a.months},
          "inputs": {"repos": a.repo, "me": a.me, "agent": a.agent, "chat_paths": a.chat,
                     "risky_regex": a.risky_regex, "god_file_loc": a.god_loc},
          "git": git_ev, "chat": chat}
    out = HOME / "evidence" / f"evidence-{TODAY().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ev, indent=2, default=str))
    comb = git_ev.get("combined", {})
    print(f"Evidence written: {out}")
    print(f"Window {ev['window']['since']} -> {ev['window']['until']} | repos: {', '.join(git_ev['repos']) or 'none'}")
    if comb:
        print(f"Owned commits: {comb['commits_owned']} (agent {comb['commits_agent']}) | median files/commit "
              f"{comb['median_files_per_commit']} | conventional {comb['conventional_pct']}% | test colocation {comb['test_colocation_pct']}%")
    print("Chat:", "no export given" if chat is None else (f"{chat['user_messages']} user messages in window" if chat.get("available") else chat["note"]))
    for n in git_ev.get("notes", []):
        print("NOTE:", n)


def cmd_suggest(a):
    ev = latest_evidence(a.evidence)
    rows = []
    for gid, g in LIB["gaps"].items():
        fired, unassessed = [], []
        for d in g["detectors"]:
            v = get_metric(d["metric"], ev)
            if v is None:
                unassessed.append(d["metric"])
            elif OPS[d["op"]](v, d["value"]):
                fired.append(f"{d['metric']}={v} ({d['op']} {d['value']})")
        assessable = len(g["detectors"]) - len(unassessed)
        rows.append({"gap": gid, "fired": fired, "unassessed": unassessed,
                     "score": round(len(fired) / assessable, 2) if assessable else 0.0})
    rows.sort(key=lambda r: -r["score"])
    print(json.dumps(rows, indent=2) if a.json else "\n".join(
        f"{r['score']:.2f}  {r['gap']:<28} fired: {'; '.join(r['fired']) or '-'}"
        + (f"  [unassessed: {', '.join(r['unassessed'])}]" if r["unassessed"] else "") for r in rows))


# ---------- import / plan ----------
def validate_eval(e):
    errs = []
    if not e.get("verdict"):
        errs.append("missing verdict")
    for d, v in (e.get("scores") or {}).items():
        if d not in LIB["dimensions"]:
            errs.append(f"unknown dimension {d}")
        elif not (1 <= float(v.get("score", 0)) <= 5) or v.get("confidence") not in ("low", "med", "high"):
            errs.append(f"{d}: need score 1-5 and confidence low|med|high")
    if not e.get("scores"):
        errs.append("missing scores")
    ranks = [g.get("rank") for g in e.get("gaps", [])]
    if not ranks or len(set(ranks)) != len(ranks):
        errs.append("gaps need unique ranks")
    for g in e.get("gaps", []):
        if g.get("id") not in LIB["gaps"]:
            errs.append(f"unknown gap id {g.get('id')}")
            continue
        ids = {t["id"] for t in LIB["gaps"][g["id"]]["tasks"]}
        for k in ("include_tasks", "skip_tasks"):
            errs += [f"{g['id']}.{k}: unknown task {t}" for t in g.get(k, []) if t not in ids]
        for i, t in enumerate(g.get("custom_tasks", []), 1):
            if t.get("technique") not in LIB["techniques"]:
                errs.append(f"{g['id']}.custom_tasks[{i}]: technique must be one of {', '.join(LIB['techniques'])}")
            if t.get("kind") not in ("quiz", "attest"):
                errs.append(f"{g['id']}.custom_tasks[{i}]: kind must be quiz|attest (metric tasks come from the library)")
            if not t.get("title") or len(t.get("do", "")) < 20:
                errs.append(f"{g['id']}.custom_tasks[{i}]: needs title and a concrete `do` (>= 20 chars)")
    return errs


def cond_true(c, ev):
    v = get_metric(c["metric"], ev)
    return v is not None and OPS[c["op"]](v, c["value"])


def select_tasks(gid, ev, ge):
    """Library tasks gated by evidence (`when`), minus skips, plus agent-authored custom tasks."""
    inc, skip = set(ge.get("include_tasks", [])), set(ge.get("skip_tasks", []))
    defs = []
    for t in LIB["gaps"][gid]["tasks"]:
        if t["id"] in skip:
            continue
        if t.get("when") and t["id"] not in inc and not any(cond_true(c, ev) for c in t["when"]):
            continue
        defs.append({**{k: v for k, v in t.items() if k != "when"}, "source": "library"})
    for i, t in enumerate(ge.get("custom_tasks", []), 1):
        defs.append({"id": f"x{i}", "kind": t["kind"], "technique": t["technique"], "title": t["title"], "do": t["do"],
                     "evidence_ref": t.get("evidence_ref"), "source": "custom"})
    return defs


def build_context(ev, risky_rx):
    ctx = {"god_files": [], "hotspots": [], "largest_commits": [], "risky_paths": []}
    inputs = ev.get("inputs", {})
    for name, m in (ev.get("git", {}).get("repos") or {}).items():
        repo_abs = next((Path(r).expanduser() for r in inputs.get("repos", []) if Path(r).expanduser().name == name),
                        HOME / "cache" / name)
        for f in m.get("largest_files", []):
            if f["loc"] > m["god_file_loc_threshold"]:
                ctx["god_files"].append({"repo": name, "path": f["path"], "loc": f["loc"], "abs": str(repo_abs / f["path"])})
        ctx["hotspots"] += [{"repo": name, **h} for h in m.get("hotspots", [])[:5]]
        ctx["largest_commits"] += [{"repo": name, **c} for c in m.get("largest_commits", [])]
        ctx["risky_paths"] += [h["path"] for h in m.get("hotspots", []) if re.search(risky_rx, h["path"], re.I)]
    ctx["god_files"].sort(key=lambda x: -x["loc"])
    return ctx


def save_report(s, src):
    src = Path(src).expanduser()
    if not src.exists():
        sys.exit(f"report file not found: {src}")
    dest_dir = HOME / "reports"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"eval-{TODAY().isoformat()}.md"
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    shutil.copyfile(dest, dest_dir / "latest.md")
    s.setdefault("evaluation", {})["report_path"] = str(dest)
    return dest


def cmd_import(a):
    e = json.loads(Path(a.evaluation).read_text())
    errs = validate_eval(e)
    if errs:
        sys.exit("evaluation.json invalid:\n  - " + "\n  - ".join(errs))
    ev = latest_evidence(a.evidence)
    s = load(required=False) or {"schema": 2, "history": [], "ledger": []}
    if s.get("evaluation"):
        s["history"].append({"date": s["evaluation"].get("date"), "verdict": s["evaluation"]["verdict"],
                             "scores": {d: v["score"] for d, v in s["evaluation"]["scores"].items()}})
    inp, prev = ev.get("inputs", {}), (s.get("settings") or {})
    mode, auto = (a.mode, False) if a.mode else (prev.get("mode", DEFAULTS["mode"]), prev.get("auto_escalate", True))
    s["settings"] = {**DEFAULTS, **prev, "mode": mode, "auto_escalate": auto,
                     "repos": inp.get("repos", []), "me": inp.get("me"), "agent": inp.get("agent"),
                     "chat_paths": inp.get("chat_paths"), "window_months": ev["window"]["months"],
                     "risky_regex": inp.get("risky_regex") or DEFAULTS["risky_regex"],
                     "god_file_loc": inp.get("god_file_loc") or DEFAULTS["god_file_loc"]}
    s["evaluation"] = {**e, "date": TODAY().isoformat()}
    if a.report:
        save_report(s, a.report)
    start = TODAY()
    plan = {"start": start.isoformat(), "context": build_context(ev, s["settings"]["risky_regex"]), "gaps": {}}
    for g in sorted(e["gaps"], key=lambda x: x["rank"]):
        lib = LIB["gaps"][g["id"]]
        span = min(90, 30 + 15 * (g["rank"] - 1))
        defs = select_tasks(g["id"], ev, g)
        n = len(defs)
        tasks = {t["id"]: {"status": "todo", "due": (start + timedelta(days=round(span * (i + 1) / n))).isoformat()}
                 for i, t in enumerate(defs)}
        base = {d["metric"]: get_metric(d["metric"], ev) for d in lib["detectors"]}
        plan["gaps"][g["id"]] = {"rank": g["rank"], "status": "active", "mode": None, "evidence": g.get("evidence", []),
                                 "baseline": base, "task_defs": defs, "tasks": tasks,
                                 "signal_defs": lib["success_signals"], "signals": {}}
    s["plan"] = plan
    log(s, type="plan", gaps=list(plan["gaps"]))
    save(s)
    (HOME / "evaluations").mkdir(parents=True, exist_ok=True)
    (HOME / "evaluations" / f"eval-{start.isoformat()}.json").write_text(json.dumps(e, indent=2))
    quiz = sum(1 for g in plan["gaps"].values() for t in g["task_defs"] if t["kind"] == "quiz")
    print(f"Plan created: {len(plan['gaps'])} gaps, {sum(len(g['task_defs']) for g in plan['gaps'].values())} tasks "
          f"({quiz} quiz lessons, chosen from your evidence). Mode: {mode}" + (" (auto-escalates after 7 days)" if auto and mode == "nudge" else ""))
    for gid, g in plan["gaps"].items():
        kinds = ", ".join(sorted({t["technique"] for t in g["task_defs"]}))
        print(f"  #{g['rank']} {gid}: {len(g['task_defs'])} tasks | techniques: {kinds}")
    print("Next: `coach.py report`, then `coach.py module <gap>`; hooks only with your consent (`install-hooks`).")


# ---------- LMS loop ----------
def fill(text, ctx):
    gf = ctx.get("god_files", [])
    rep = {"{god_file_1}": gf[0]["path"] if gf else "your largest file",
           "{largest_commit}": (lambda c: f"commit {c['sha']} ({c['files']} files: \"{c['subject']}\")")(
               max(ctx["largest_commits"], key=lambda c: c["files"])) if ctx.get("largest_commits") else "your largest recent commit",
           "{risky_path_1}": ctx["risky_paths"][0] if ctx.get("risky_paths") else "a route that touches auth/tenant data"}
    for k, v in rep.items():
        text = text.replace(k, v)
    return text


def describe_verify(t):
    if t["kind"] == "metric":
        v = t["verify"]
        return f"automatic: `{v['metric']} {v['op']} {v['value']}`" + (f" over >= {v['min_commits']} commits" if v.get("min_commits") else "") + " (run `coach.py verify`)"
    return {"attest": "evidence note (commit, PR, file) via `coach.py task ... done --note`",
            "quiz": "in-session check, then `coach.py task ... done --note \"passed 3/3\"` (re-tested at +3/+10/+30 days)"}[t["kind"]]


def tech_name(t):
    return LIB["techniques"].get(t.get("technique"), {}).get("name", t.get("technique", "-"))


def cmd_module(a):
    s = load()
    g = s["plan"]["gaps"].get(a.gap) or sys.exit(f"{a.gap} is not in your plan. In plan: {', '.join(s['plan']['gaps'])}")
    lib, ctx = LIB["gaps"][a.gap], s["plan"]["context"]
    out = [f"# Module: {lib['title']}", "",
           f"Plan rank #{g['rank']} | status: {g['status']} | enforcement: {effective_mode(s, g)}", "",
           "## Why this is on your plan", *([f"- {x}" for x in g["evidence"]] or ["- (no evidence recorded)"]),
           "", "Baseline when the plan was created: " + (", ".join(f"{k}={v}" for k, v in g["baseline"].items() if v is not None) or "n/a"),
           "", "## What senior looks like", lib["senior_looks_like"], "", f"Why it matters: {lib['why']}", "",
           "## How this gap closes best", " -> ".join(LIB["techniques"][x]["name"] for x in lib["closes_by"]),
           "", "## Tasks (selected from your evidence)"]
    for t in g["task_defs"]:
        st = g["tasks"][t["id"]]
        out += [f"### {t['id']} [{t['kind']} | {tech_name(t)}] {t['title']}  (due {st['due']}, {st['status']})",
                fill(t["do"], ctx), f"Verified by: {describe_verify(t)}", ""]
    out += ["## Success signals"] + [f"- {x['metric']} {x['op']} {x['value']}" + (f" over last {x['window_days']} days" if x.get("window_days") else f" by day {x.get('by_day')}") for x in g["signal_defs"]]
    out += ["", "## What the live checks will say about this gap", "Rules: " + ", ".join(lib["rules"])]
    txt = "\n".join(out)
    (HOME / "modules").mkdir(parents=True, exist_ok=True)
    (HOME / "modules" / f"{a.gap}.md").write_text(txt)
    print(txt)


def open_tasks(s, gid):
    g = s["plan"]["gaps"][gid]
    return [(t, g["tasks"][t["id"]]) for t in g["task_defs"] if g["tasks"][t["id"]]["status"] in ("todo", "in_progress")]


def overdue(s, gid):
    return [t for t, st in open_tasks(s, gid) if st["due"] < TODAY().isoformat()]


def effective_mode(s, g):
    cfg = s["settings"]
    mode = g.get("mode") or cfg["mode"]
    if mode == "nudge" and cfg.get("auto_escalate") and not g.get("mode"):
        if TODAY() >= datetime.fromisoformat(s["plan"]["start"]).date() + timedelta(days=7):
            return "escalate"
    return mode


def due_reviews(s):
    out = []
    for gid, g in s["plan"]["gaps"].items():
        for tid, st in g["tasks"].items():
            out += [(gid, tid, r["due"]) for r in st.get("reviews", []) if not r.get("done") and r["due"] <= TODAY().isoformat()]
    return sorted(out, key=lambda x: x[2])


def cmd_status(a):
    s = load()
    g0 = next(iter(s["plan"]["gaps"].values()))
    print(f"Verdict: {s['evaluation']['verdict']} | plan start {s['plan']['start']} | mode {s['settings']['mode']} (now: {effective_mode(s, g0)})")
    print(f"{'#':<3}{'gap':<28}{'status':<10}{'tasks':<8}{'overdue':<8}{'overrides30d':<13}signals")
    for gid, g in sorted(s["plan"]["gaps"].items(), key=lambda x: x[1]["rank"]):
        done = sum(1 for t in g["tasks"].values() if t["status"] in ("done", "verified"))
        ov = sum(1 for e in s["ledger"] if e.get("type") == "override" and e.get("gap") == gid and ago(e["ts"], days=30))
        sig = ", ".join(f"{k}:{'met' if v['met'] else 'no'}" for k, v in g["signals"].items()) or "not verified yet"
        print(f"{g['rank']:<3}{gid:<28}{g['status']:<10}{done}/{len(g['tasks']):<6}{len(overdue(s, gid)):<8}{ov:<13}{sig}")
    rv = due_reviews(s)
    if rv:
        print(f"Reviews due: {len(rv)} (run `coach.py next`)")
    if s.get("history"):
        print("Previous evaluations:", "; ".join(f"{h['date']}: {h['verdict']}" for h in s["history"]))


def cmd_next(a):
    s = load()
    for gid, tid, due in due_reviews(s)[:2]:
        t = next(t for t in s["plan"]["gaps"][gid]["task_defs"] if t["id"] == tid)
        print(f"[review due {due}] [{gid}] {tid} {t['title']} -- re-test from memory (no AI), then: coach.py task {gid} {tid} review --note \"...\"")
    for gid, g in sorted(s["plan"]["gaps"].items(), key=lambda x: x[1]["rank"]):
        if g["status"] == "mastered":
            continue
        ot = open_tasks(s, gid)
        if ot:
            t, st = ot[0]
            print(f"[{gid}] {t['id']} ({t['kind']} | {tech_name(t)}) {t['title']} -- due {st['due']}" + ("  ** OVERDUE **" if st["due"] < TODAY().isoformat() else ""))
            print(fill(t["do"], s["plan"]["context"]))
            print(f"Verified by: {describe_verify(t)}")
            return
    print("No open tasks. Run `coach.py verify` to confirm signals, or re-evaluate.")


def cmd_task(a):
    s = load()
    g = s["plan"]["gaps"].get(a.gap) or sys.exit("gap not in plan")
    t = next((t for t in g["task_defs"] if t["id"] == a.task), None) or sys.exit("unknown task for this gap (the plan only contains tasks selected from your evidence)")
    st = g["tasks"][a.task]
    if a.action == "start":
        st.update(status="in_progress", started=TODAY().isoformat())
    elif a.action == "review":
        r = next((r for r in st.get("reviews", []) if not r.get("done") and r["due"] <= TODAY().isoformat()), None)
        if not r:
            sys.exit("No review due for this task.")
        if len((a.note or "").strip()) < 20:
            sys.exit("Review needs a note (>= 20 chars): what you recalled without AI, and what you missed.")
        r.update(done=True, note=a.note, completed=TODAY().isoformat())
    else:
        if t["kind"] == "metric":
            sys.exit("Metric tasks are verified from your history. Do the work, then run `coach.py verify`.")
        if len((a.note or "").strip()) < 20:
            sys.exit("Completion needs an evidence note (>= 20 chars): commit hash, PR link, file, or 'passed 3/3 on <topic>'.")
        st.update(status="done", completed=TODAY().isoformat(), note=a.note)
        if t["kind"] == "quiz" or LIB["techniques"].get(t.get("technique"), {}).get("spaced"):
            st["reviews"] = [{"due": (TODAY() + timedelta(days=d)).isoformat(), "done": False} for d in (3, 10, 30)]
    log(s, type="task", gap=a.gap, task=a.task, action=a.action)
    save(s)
    print(f"{a.gap}/{a.task}: {st['status']}" + (f" | reviews scheduled: {', '.join(r['due'] for r in st['reviews'])}" if st.get("reviews") and a.action == "done" else ""))


def cmd_verify(a):
    s = load()
    cfg = s["settings"]
    chat_paths = [a.chat] if a.chat else cfg.get("chat_paths")
    cache = {}

    def evidence(since, scan):
        k = (since.date(), scan)
        if k not in cache:
            git_ev = G.collect(cfg["repos"], since, cfg.get("me"), cfg.get("agent"), scan, False,
                               {"risky_regex": cfg["risky_regex"], "god_file_loc": cfg["god_file_loc"]}, HOME / "cache")
            chat = C.collect(chat_paths, since) if chat_paths else None
            cache[k] = {"git": git_ev, "chat": chat}
        return cache[k]

    def measure(spec, since_floor):
        window = spec.get("window_days")
        since = max(datetime.fromisoformat(since_floor).replace(tzinfo=timezone.utc),
                    NOW() - timedelta(days=window)) if window else datetime.fromisoformat(since_floor).replace(tzinfo=timezone.utc)
        ev = evidence(since, spec["metric"].endswith("secret_signal_count"))
        v = get_metric(spec["metric"], ev, state=s)
        n = (ev["git"].get("combined") or {}).get("commits_owned", 0) if spec["metric"].startswith("git.") else (ev["chat"] or {}).get("user_messages", 0) if spec["metric"].startswith("chat.") else 10**9
        if spec.get("min_commits") and n < spec["min_commits"]:
            return v, f"insufficient data ({n}/{spec['min_commits']} since {since.date()})"
        if v is None:
            return None, "unassessed (no data/path)"
        return v, "met" if OPS[spec["op"]](v, spec["value"]) else "not met"

    targets = [a.gap] if a.gap else list(s["plan"]["gaps"])
    for gid in targets:
        g = s["plan"]["gaps"][gid]
        print(f"\n[{gid}]")
        for t in g["task_defs"]:
            if t["kind"] == "metric" and g["tasks"][t["id"]]["status"] != "verified":
                v, res = measure(t["verify"], g["tasks"][t["id"]].get("started") or s["plan"]["start"])
                print(f"  task {t['id']}: {t['verify']['metric']}={v} -> {res}")
                if res == "met":
                    g["tasks"][t["id"]].update(status="verified", completed=TODAY().isoformat())
        for sig in g["signal_defs"]:
            v, res = measure(sig, s["plan"]["start"])
            by = (datetime.fromisoformat(s["plan"]["start"]) + timedelta(days=sig["by_day"])).date().isoformat() if sig.get("by_day") else None
            late = " (past its by-day date)" if by and res != "met" and by < TODAY().isoformat() else ""
            g["signals"][sig["id"]] = {"value": v, "met": res == "met", "result": res, "checked": TODAY().isoformat()}
            print(f"  signal {sig['id']}: {sig['metric']}={v} target {sig['op']} {sig['value']} -> {res}{late}")
        all_tasks = all(t["status"] in ("done", "verified") for t in g["tasks"].values())
        if all_tasks and g["signals"] and all(x["met"] for x in g["signals"].values()):
            if g["status"] != "mastered":
                g.update(status="mastered", mastered=TODAY().isoformat())
                print("  => MASTERED. Live checks for this gap drop to info-level (regressions reopen it).")
        log(s, type="verify", gap=gid)
    save(s)


def cmd_report(a):
    s = load()
    if a.save:
        dest = save_report(s, a.save)
        save(s)
        print(f"Report saved: {dest}")
    e = s["evaluation"]
    print(f"Evaluation {e['date']} | window {e.get('window_months', s['settings'].get('window_months'))} months | verdict: {e['verdict']}")
    print(f"{'dimension':<18}{'score':<7}{'conf':<6}evidence")
    for d, v in sorted(e["scores"].items(), key=lambda x: x[1]["score"]):
        print(f"{d:<18}{v['score']:<7}{v['confidence']:<6}{(v.get('evidence') or ['-'])[0][:70]}")
    print("\nGaps (plan order):")
    for gid, g in sorted(s["plan"]["gaps"].items(), key=lambda x: x[1]["rank"]):
        print(f"  #{g['rank']} {gid}: {len(g['task_defs'])} tasks | " + "; ".join(g["evidence"][:2]))
    if e.get("unassessed"):
        print("Not assessed:", ", ".join(e["unassessed"]))
    rp = e.get("report_path")
    print(f"\nFull report: {rp}" if rp and Path(rp).exists() else "\nNo full report saved yet (`coach.py report --save FILE`).")


# ---------- live accountability ----------
class Check:
    def __init__(self, s, event, cwd, stateless):
        self.s, self.event, self.cwd, self.stateless = s, event, cwd, stateless
        self.cfg = (s or {}).get("settings", DEFAULTS) if s else DEFAULTS
        self.findings = []

    def plan_gap(self, gids):
        if self.stateless:
            return gids[0]
        plan = (self.s or {}).get("plan", {}).get("gaps", {})
        return next((g for g in gids if g in plan), None)

    def severity(self, gid, weight):
        if weight == "critical":
            return "block"
        if self.stateless:
            return "warn"
        g = self.s["plan"]["gaps"][gid]
        if g["status"] == "mastered":
            return "info"
        mode = effective_mode(self.s, g)
        if mode == "off":
            return None
        if mode == "gate":
            return "block" if weight == "hard" else "warn"
        if mode == "escalate" and weight == "hard":
            ignored = sum(1 for e in self.s["ledger"] if e.get("type") == "finding" and e.get("gap") == gid
                          and e.get("sev") in ("warn", "block") and ago(e["ts"], days=7))
            if overdue(self.s, gid) or ignored >= 3:
                return "block"
        return "warn"

    def emit(self, rule, gids, weight, msg, fix, agent=""):
        gid = self.plan_gap(gids)
        if not gid:
            return
        sev = self.severity(gid, weight)
        if not sev:
            return
        if self.event == "prompt" and not self.stateless and any(
                e.get("rule") == rule and ago(e["ts"], minutes=10) for e in self.s["ledger"][-50:]):
            return
        task = None
        if not self.stateless and self.s["plan"]["gaps"][gid]["status"] != "mastered":
            ot = open_tasks(self.s, gid)
            if ot:
                t, st = ot[0]
                task = f"{t['id']} \"{t['title']}\" (due {st['due']}{', OVERDUE' if st['due'] < TODAY().isoformat() else ''}) -- run: coach.py next"
        self.findings.append({"rule": rule, "gap": gid, "sev": sev, "msg": msg, "fix": fix, "task": task, "agent": agent})


def diff_rows(cwd, mode, base=None):
    cmd = {"staged": ["diff", "--cached", "--numstat"], "worktree": ["diff", "HEAD", "--numstat"],
           "range": ["diff", "--numstat", f"{base}...HEAD"]}[mode]
    rows = []
    for line in git(cmd, cwd).splitlines():
        m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", line)
        if m and not P.is_noise(G._clean_path(m.group(3))):
            rows.append((G._clean_path(m.group(3)), 0 if m.group(1) == "-" else int(m.group(1)), 0 if m.group(2) == "-" else int(m.group(2))))
    if mode == "worktree":
        for u in git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines():
            if not P.is_noise(u):
                rows.append((u, G._loc(Path(cwd) / u) or 0, 0))
    return rows


def secret_hits(diff_text):
    cur, hits = None, []
    for ln in diff_text.splitlines():
        if ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("+") and not ln.startswith("+++") and P.secret_kind(ln):
            hits.append(f"{cur} ({P.secret_kind(ln)})")
    return sorted(set(hits))


def emit_secrets(c, hits, where):
    if hits:
        c.emit("secret-in-diff", ["security-hygiene", "operational-predictability"], "critical",
               f"Possible secret in {where}: {', '.join(hits[:3])}.",
               "Remove it, load from the environment, and rotate it if it was ever real.",
               agent="Do not commit this value. Move it to environment config and tell the developer to rotate it.")


def default_base(cwd):
    for ref in ("@{upstream}", "origin/HEAD", "origin/main", "origin/master", "main", "master"):
        if git(["rev-parse", "--verify", "-q", ref], cwd).strip():
            return ref
    return "HEAD~20"


def run_check(c, a):
    cwd, cfg, ev = c.cwd, c.cfg, c.event
    risky_rx = re.compile(cfg["risky_regex"], re.I)
    if ev == "prompt":
        text = a.text or ""
        if a.stdin_json:
            try:
                text = json.loads(sys.stdin.read()).get("prompt", "")
            except json.JSONDecodeError:
                return
        elif not text and not sys.stdin.isatty():
            text = sys.stdin.read()
        words = len(text.split())
        if words < 8 or text.strip().startswith("/") or (text.strip().endswith("?") and not C.IMPERATIVE.search(text)):
            return
        if not re.search(r"\b(implement|refactor|add|build|create|fix|change|write|update|migrate)\b", text, re.I):
            return
        missing = [n for n, ok in (("constraints / non-goals", C.CONSTRAINT.search(text)), ("required tests", C.TESTWORD.search(text)),
                                   ("allowed files or scope", C.PATHLIKE.search(text) or C.SCOPE.search(text))) if not ok]
        if len(missing) >= 2:
            c.emit("prompt-contract", ["ai-ownership", "requirements-clarity"], "soft",
                   f"Prompt is missing: {', '.join(missing)}.", "Add goal, non-goals, allowed files, acceptance criteria, required tests.",
                   agent="Before writing code, ask the developer for the missing pieces (or state your assumptions explicitly and get a yes).")
        return
    if ev == "commit-msg":
        raw = Path(a.msg_file).read_text(errors="replace") if a.msg_file else ""
        subj = next((l for l in raw.splitlines() if l.strip() and not l.startswith("#")), "").strip()
        if subj and not re.match(r"^(Merge|Revert|fixup!|squash!)", subj) and not P.CONVENTIONAL.match(subj):
            c.emit("commit-message-quality", ["change-hygiene"], "soft", f"Subject is not `type(scope): why`: \"{subj[:60]}\"",
                   "e.g. fix(billing): stop double-charging on retry")
        staged = [r[0] for r in diff_rows(cwd, "staged")]
        if P.FIX_SUBJECT.match(subj) and any(P.is_source(p) for p in staged) and not any(P.is_test(p) for p in staged):
            c.emit("fix-without-test", ["debugging-method", "test-as-gate"], "soft", "Fix commit without a regression test.",
                   "Add the failing test first, then the fix, in the same commit.")
        return
    if ev in ("pre-commit", "agent-done"):
        rows = diff_rows(cwd, "staged" if ev == "pre-commit" else "worktree")
        files = [r[0] for r in rows]
        lines = sum(r[1] + r[2] for r in rows)
        cap = cfg["commit_file_cap"] if ev == "pre-commit" else cfg["pr_file_cap"]
        if len(files) > cap:
            c.emit("commit-files-cap", ["change-hygiene"], "hard" if len(files) > 2 * cap else "soft",
                   f"{len(files)} files in this change (cap {cap}).", "Split by concern; land each slice separately.",
                   agent="Stop and propose a split into smaller changes before continuing; do not expand scope.")
        src = [p for p in files if P.is_source(p)]
        has_test = any(P.is_test(p) for p in files)
        risky = [p for p in src if risky_rx.search(p)]
        if risky and not has_test:
            c.emit("risky-without-test", ["security-hygiene", "test-as-gate"], "hard",
                   f"Auth/tenant/billing-related files changed without tests: {', '.join(risky[:3])}.",
                   "Add deny + wrong-scope + happy-path tests in the same change.",
                   agent="Write the missing deny/scope/happy-path tests before reporting this work as done.")
        elif src and not has_test and lines >= 50:
            c.emit("src-without-test", ["test-as-gate"], "soft", f"{len(src)} source files, {lines} lines changed, no tests.",
                   "Land the test with the change.")
        god = {g["path"] for g in (c.s or {}).get("plan", {}).get("context", {}).get("god_files", [])} if c.s else set()
        for p, add, dele in rows:
            if not P.is_source(p):
                continue
            head_loc = len(git(["show", f"HEAD:{p}"], cwd).splitlines())
            if (head_loc > cfg["god_file_loc"] or p in god) and add - dele > 20:
                c.emit("god-file-growth", ["modular-architecture"], "hard" if add - dele > 150 else "soft",
                       f"{p} is already {head_loc} lines and grows by {add - dele}.", "Put new logic in a new module; call it from here.",
                       agent=f"Do not add this logic to {p}; create a new module and call it from there.")
                break
        if ev == "agent-done" and (len(files) > cfg["pr_file_cap"] // 2 or lines > cfg["pr_line_cap"] // 2):
            branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()
            head_ts = git(["log", "-1", "--format=%cI"], cwd).strip() or "1970-01-01T00:00:00+00:00"
            if not c.stateless and not any(e.get("kind") == "blast-radius" and e.get("branch") == branch
                                           and e["ts"] >= datetime.fromisoformat(head_ts).astimezone(timezone.utc).isoformat() for e in c.s["ledger"]):
                c.emit("blast-radius-note", ["ai-ownership"], "soft", f"{len(files)} files / {lines} lines changed by an agent with no blast-radius note.",
                       "Write 5 bullets (callers, auth, data, UI, rollback): coach.py note --kind blast-radius --text '...'",
                       agent="Ask the developer for a blast-radius note (callers, auth, data, UI, rollback) before calling this finished.")
        hits = secret_hits(git(["diff", "--cached" if ev == "pre-commit" else "HEAD", "-U0"], cwd))
        if ev == "agent-done":  # agents mostly create NEW files, which `git diff HEAD` does not show
            for u in git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines():
                fp = Path(cwd) / u
                if P.is_noise(u) or not fp.is_file() or fp.stat().st_size > 1_000_000:
                    continue
                for ln in fp.read_text(errors="ignore").splitlines():
                    k = P.secret_kind(ln)
                    if k:
                        hits.append(f"{u} ({k})")
                        break
        emit_secrets(c, sorted(set(hits)), "working-tree changes" if ev == "agent-done" else "staged changes")
        return
    if ev in ("pre-push", "ci"):
        base = a.base or default_base(cwd)
        rows = diff_rows(cwd, "range", base)
        emit_secrets(c, secret_hits(git(["diff", f"{base}...HEAD", "-U0"], cwd)), f"commits since {base}")
        lines, nfiles = sum(r[1] + r[2] for r in rows), len(rows)
        if lines > cfg["pr_line_cap"] or nfiles > cfg["pr_file_cap"]:
            big = lines > 2 * cfg["pr_line_cap"] or nfiles > 2 * cfg["pr_file_cap"]
            c.emit("push-range-size", ["change-hygiene", "operational-predictability"], "hard" if big else "soft",
                   f"Pushing {lines} changed lines / {nfiles} files vs {base} (caps {cfg['pr_line_cap']} / {cfg['pr_file_cap']}).",
                   "Split into stacked PRs, one concern each; if it truly must be big, write why in the PR.")
        agent_rx = re.compile("|".join(cfg.get("agent") or []) or P.AGENT_AUTHOR_DEFAULT, re.I)
        authors = git(["log", f"{base}..HEAD", "--format=%an <%ae>"], cwd).splitlines()
        if any(agent_rx.search(x) for x in authors) and (lines > cfg["pr_line_cap"] // 2) and not c.stateless:
            branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()
            if not any(e.get("kind") == "blast-radius" and e.get("branch") == branch for e in c.s["ledger"]):
                c.emit("blast-radius-note", ["ai-ownership"], "soft", "Agent-authored commits in this push with no blast-radius note.",
                       "coach.py note --kind blast-radius --text '<callers, auth, data, UI, rollback>'")


def cmd_check(a):
    s = load(required=False)
    if a.stdin_json and a.event != "prompt":
        try:
            if json.loads(sys.stdin.read() or "{}").get("stop_hook_active"):
                return
        except json.JSONDecodeError:
            pass
    if not s and not a.stateless:
        return  # not onboarded yet: stay silent, never break someone's commit
    c = Check(s, a.event, os.getcwd(), a.stateless)
    run_check(c, a)
    if not c.findings:
        return
    override = os.environ.get("COACH_OVERRIDE", "").strip()
    stream = sys.stdout if a.out == "stdout" else sys.stderr
    blocked = [f for f in c.findings if f["sev"] == "block"]
    print(f"senior-coach [{a.event}]", file=stream)
    for f in c.findings:
        print(f"  {f['sev'].upper():<5} [{f['gap']}] {f['msg']}\n        -> {f['fix']}", file=stream)
        if f["task"]:
            print(f"        plan: {f['task']}", file=stream)
        if a.audience == "agent" and f["agent"]:
            print(f"        agent instruction: {f['agent']}", file=stream)
    if s and not a.stateless:
        for f in c.findings:
            log(s, type="finding", gap=f["gap"], rule=f["rule"], sev=f["sev"], event=a.event)
            if f["sev"] == "info":  # regression watch on mastered gaps
                g = s["plan"]["gaps"][f["gap"]]
                if sum(1 for e in s["ledger"] if e.get("gap") == f["gap"] and e.get("sev") == "info" and ago(e["ts"], days=14)) >= 3:
                    g["status"] = "active"
                    print(f"  REOPENED [{f['gap']}]: 3 regressions in 14 days.", file=stream)
        if blocked and len(override) >= 8:
            for f in blocked:
                log(s, type="override", gap=f["gap"], rule=f["rule"], reason=override[:200])
            print(f"  Override accepted and logged: {override[:80]}", file=stream)
            blocked = []
        if blocked and a.event == "agent-done":  # Stop-hook loop guard: block once per exact diff
            fp = hashlib.sha1((git(["diff", "HEAD", "--numstat"]) + git(["ls-files", "--others", "--exclude-standard"])).encode()).hexdigest()[:12]
            if any(e.get("type") == "stop-block" and e.get("fp") == fp and ago(e["ts"], minutes=30) for e in s["ledger"]):
                print("  (already blocked once for this exact diff; not blocking again)", file=stream)
                blocked = []
            else:
                log(s, type="stop-block", fp=fp)
        save(s)
    if blocked:
        print("  Blocked." + ("" if a.stateless else " To proceed anyway (logged, counts against this gap): "
              "COACH_OVERRIDE='reason of at least 8 chars' <same command>"), file=stream)
        sys.exit(a.block_exit)


def cmd_note(a):
    s = load()
    log(s, type="note", kind=a.kind, text=a.text, branch=git(["rev-parse", "--abbrev-ref", "HEAD"]).strip())
    save(s)
    print(f"{a.kind} note logged.")


AGENT_DIRS = {"claude-code": "~/.claude/skills", "cursor": "~/.cursor/skills", "codex": "~/.agents/skills",
              "gemini": "~/.gemini/skills", "agents": "~/.agents/skills"}
AGENT_PROBE = {"claude-code": "~/.claude", "cursor": "~/.cursor", "codex": "~/.codex", "gemini": "~/.gemini"}
HOOK = """#!/bin/sh
# senior-coach managed hook ({event})
HOOKDIR="$(dirname "$0")"
if [ -x "$HOOKDIR/{name}.pre-senior-coach" ]; then "$HOOKDIR/{name}.pre-senior-coach" "$@" || exit $?; fi
[ -x "{shim}" ] || exit 0   # tool removed: never break the developer's commit
exec "{shim}" check --event {event}{extra}
"""


def shim_path():
    return HOME / "bin" / "senior-coach"


def ensure_shim():
    """Stable entry point so hooks survive moving/re-cloning the skill folder (re-run `init --relink`)."""
    sp = shim_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(f'#!/bin/sh\nexec python3 "{HERE / "coach.py"}" "$@"\n')
    sp.chmod(0o755)
    return sp


def repo_hooks_dir(repo):
    hooks = Path(git(["rev-parse", "--git-path", "hooks"], repo).strip())
    return hooks if hooks.is_absolute() else repo / hooks


def cmd_install(a):
    shim = ensure_shim()
    for r in a.repo or ["."]:
        repo = Path(r).resolve()
        if not git(["rev-parse", "--git-dir"], repo).strip():
            print(f"{repo}: not a git repository, skipped")
            continue
        custom = git(["config", "core.hooksPath"], repo).strip()
        if custom:
            tracked = (repo / custom).resolve() if not Path(custom).is_absolute() else Path(custom)
            if str(tracked).startswith(str(repo)):
                print(f"{repo.name}: core.hooksPath={custom} (husky or a tracked hooks folder). Not touching it. Add this line to its "
                      f"pre-commit / commit-msg / pre-push scripts instead:\n  \"{shim}\" check --event <pre-commit|commit-msg|pre-push>"
                      + (' --msg-file "$1"' if False else "") + "\n  (commit-msg also needs: --msg-file \"$1\")")
                continue
        hooks = repo_hooks_dir(repo)
        hooks.mkdir(parents=True, exist_ok=True)
        for name, event, extra in (("commit-msg", "commit-msg", ' --msg-file "$1"'), ("pre-commit", "pre-commit", ""), ("pre-push", "pre-push", "")):
            f = hooks / name
            if f.exists() and "senior-coach" not in f.read_text(errors="ignore"):
                f.rename(hooks / f"{name}.pre-senior-coach")
            f.write_text(HOOK.format(event=event, name=name, shim=shim, extra=extra))
            f.chmod(0o755)
        print(f"{repo.name}: hooks installed in {hooks}")
    print("Bypassing with --no-verify skips local hooks; `coach.py install-ci` adds a CI backstop. Agent hooks: `coach.py integrate`.")


def render_rules(shim):
    return (ROOT / "integrations" / "agent-rules.md").read_text().replace("{{SHIM}}", str(shim))


def add_exclude(repo, pattern):
    ex = Path(git(["rev-parse", "--git-path", "info/exclude"], repo).strip())
    ex = ex if ex.is_absolute() else repo / ex
    ex.parent.mkdir(parents=True, exist_ok=True)
    cur = ex.read_text() if ex.exists() else ""
    if pattern not in cur.splitlines():
        ex.write_text(cur + ("" if cur.endswith("\n") or not cur else "\n") + pattern + "\n")


def cmd_integrate(a):
    shim = ensure_shim()
    if a.agent == "claude-code":
        path = Path(a.settings or "~/.claude/settings.json").expanduser()
        try:
            data = json.loads(path.read_text()) if path.exists() else {}
        except json.JSONDecodeError:
            sys.exit(f"{path} is not valid JSON; fix it first (nothing was changed).")
        hooks = data.setdefault("hooks", {})
        want = {"UserPromptSubmit": f'"{shim}" check --event prompt --stdin-json --out stdout --audience agent',
                "Stop": f'"{shim}" check --event agent-done --stdin-json --audience agent --block-exit 2'}
        changed = []
        for ev, cmd in want.items():
            lst = hooks.setdefault(ev, [])
            if not any("senior-coach" in h.get("command", "") for grp in lst for h in grp.get("hooks", [])):
                lst.append({"hooks": [{"type": "command", "command": cmd}]})
                changed.append(ev)
        if a.dry_run:
            print(json.dumps({"hooks": {k: hooks[k] for k in want}}, indent=2))
            return
        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            bak = path.with_suffix(".json.senior-coach.bak")
            if path.exists() and not bak.exists():
                shutil.copyfile(path, bak)
            path.write_text(json.dumps(data, indent=2))
        print(f"Claude Code hooks {'added: ' + ', '.join(changed) if changed else 'already present'} in {path}. Restart Claude Code sessions to load them.")
        return
    for r in a.repo or ["."]:
        repo = Path(r).resolve()
        if not git(["rev-parse", "--git-dir"], repo).strip():
            print(f"{repo}: not a git repository, skipped")
            continue
        body = render_rules(shim)
        if a.agent == "cursor":
            dest = repo / ".cursor" / "rules" / "senior-coach.mdc"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body)
            add_exclude(repo, ".cursor/rules/senior-coach.mdc")
        else:
            dest = repo / "AGENTS.md"
            if dest.exists():
                print(f"{repo.name}: AGENTS.md already exists (tracked?). Not editing it. Add this block yourself if the team agrees:\n{body}")
                continue
            dest.write_text(re.sub(r"^---.*?---\n", "", body, flags=re.S))
            add_exclude(repo, "AGENTS.md")
        print(f"{repo.name}: wrote {dest} (kept out of git via .git/info/exclude)")


def upstream():
    url = git(["remote", "get-url", "origin"], ROOT).strip()
    m = re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", url)
    return (m.group(1), m.group(2)) if m else (None, None)


def cmd_install_ci(a):
    owner, name = (a.owner, "senior-dev-coach") if a.owner else upstream()
    tpl = (ROOT / "integrations" / "github-action.yml").read_text()
    if re.search(r"\bOWNER\b", tpl):
        if not owner:
            sys.exit("This clone has no GitHub origin and the workflow still says OWNER. Pass --owner <upstream owner>.")
        tpl = re.sub(r"\bOWNER\b", owner, tpl)
    if name and name != "senior-dev-coach":
        tpl = tpl.replace("/senior-dev-coach", f"/{name}")
    for r in a.repo or ["."]:
        repo = Path(r).resolve()
        dest = repo / ".github" / "workflows" / "senior-coach.yml"
        if dest.exists() and not a.force:
            print(f"{repo.name}: {dest} exists, skipped (--force to overwrite)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(tpl)
        print(f"{repo.name}: created {dest} (NOT committed). It adds a file to the repo: get team buy-in before committing in a work repo.")


def cmd_set_owner(a):
    """Maintainer-only. Edits tracked files in this clone; run once before the first push."""
    total = 0
    for f in ("README.md", "INSTALL.md", "integrations/github-action.yml"):
        p = ROOT / f
        if not p.exists():
            continue
        txt = p.read_text()
        new, n = re.subn(r"\bOWNER\b", a.owner, txt)
        total += n
        print(f"{f}: {n} replacement(s)")
        if n and not a.dry_run:
            p.write_text(new)
    print("dry run, nothing written." if a.dry_run else f"Done ({total}). Review with `git diff`, commit, push. End users should never run this.")


def cmd_init(a):
    shim = ensure_shim()
    chosen = a.agent or [k for k, v in AGENT_PROBE.items() if Path(v).expanduser().exists()]
    if not chosen:
        sys.exit("No agent detected. Pass --agent claude-code|cursor|codex|gemini|agents")
    installed = []
    for ag in chosen:
        d = Path(AGENT_DIRS[ag]).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        link = d / "senior-dev-coach"
        if link.is_symlink() or link.exists():
            if link.is_symlink() and Path(os.readlink(link)).resolve() == ROOT.resolve():
                print(f"{ag}: already linked ({link})")
                installed.append({"agent": ag, "path": str(link)})
                continue
            if a.relink and link.is_symlink():
                link.unlink()
            else:
                print(f"{ag}: {link} exists and points elsewhere; use --relink to repoint it (symlinks only).")
                continue
        try:
            link.symlink_to(ROOT, target_is_directory=True)
            print(f"{ag}: linked {link} -> {ROOT}")
        except OSError:
            shutil.copytree(ROOT, link, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            print(f"{ag}: symlinks unavailable, copied to {link} (re-run init after `git pull`)")
        installed.append({"agent": ag, "path": str(link)})
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / "install.json").write_text(json.dumps({"skill_root": str(ROOT), "shim": str(shim), "agents": installed,
                                                    "installed_at": NOW().isoformat(timespec="seconds")}, indent=2))
    print(f"Shim: {shim}  (add {shim.parent} to PATH to type `senior-coach ...`)")
    if "claude-code" in chosen:
        print("Note: personal Claude Code skills do not load in Cowork or cloud sessions. Start a new Claude Code session to pick the skill up.")
    print("Next: open your agent and say: Evaluate me as a developer.  (It will run `discover` and confirm what it finds with you.)")


def _git_authors(repo, since="12.months"):
    out = G.run(["git", "shortlog", "-sne", "--since=" + since, "HEAD"], repo)
    res = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(.*)$", line)
        if m:
            res.append({"commits": int(m.group(1)), "author": m.group(2)})
    return res


def cmd_discover(a):
    """Read-only inventory so the agent can pre-fill intake. Never reads chat contents, only sniffs file types."""
    home = Path.home()
    roots = [Path(r).expanduser() for r in (a.root or ["~/code", "~/dev", "~/projects", "~/src", "~/work", "~/repos", "~/Documents/GitHub", "~/GitHub"])]
    skip = {"node_modules", ".venv", "venv", "dist", "build", "target", ".cache", ".Trash", "Library"}
    repo_paths = []
    for root in roots:
        if not root.is_dir():
            continue
        base = len(root.parts)
        for dp, dns, _ in os.walk(root):
            if (Path(dp) / ".git").exists():
                repo_paths.append(Path(dp))
                dns[:] = []
                continue
            dns[:] = [d for d in dns if d not in skip and not d.startswith(".")] if len(Path(dp).parts) - base < 3 else []
    gl_email = git(["config", "--global", "user.email"], home).strip()
    gl_name = git(["config", "--global", "user.name"], home).strip()
    identities, repos, agent_authors = {x for x in (gl_email, gl_name) if x}, [], set()
    agent_rx = re.compile(P.AGENT_AUTHOR_DEFAULT, re.I)
    for rp in repo_paths[:60]:
        email = git(["config", "user.email"], rp).strip()
        if email:
            identities.add(email)
        authors = _git_authors(rp)
        for x in authors:
            if agent_rx.search(x["author"]):
                agent_authors.add(re.sub(r"\s*<.*>", "", x["author"]))
        mine = sum(x["commits"] for x in authors if email and email.lower() in x["author"].lower())
        url = git(["remote", "get-url", "origin"], rp).strip()
        m = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
        repos.append({"path": str(rp), "github": m.group(1) if m else None, "email_in_repo": email or None,
                      "last_commit": git(["log", "-1", "--format=%cI"], rp).strip() or None,
                      "commits_12m_total": sum(x["commits"] for x in authors), "commits_12m_by_configured_email": mine,
                      "top_authors": authors[:3]})
    repos.sort(key=lambda r: -r["commits_12m_by_configured_email"])
    chats = {"claude_code_transcripts": None, "export_candidates": [], "unsupported": []}
    cc = home / ".claude" / "projects"
    if cc.is_dir():
        files = list(cc.rglob("*.jsonl"))
        if files:
            chats["claude_code_transcripts"] = {"path": str(cc), "files": len(files),
                                                "oldest": datetime.fromtimestamp(min(f.stat().st_mtime for f in files), timezone.utc).date().isoformat(),
                                                "newest": datetime.fromtimestamp(max(f.stat().st_mtime for f in files), timezone.utc).date().isoformat()}
    import zipfile
    for d in (home / "Downloads", home / "Desktop", home / "Documents", home):
        if not d.is_dir():
            continue
        for f in list(d.iterdir())[:2000]:
            low = f.name.lower()
            try:
                if f.suffix == ".zip" and re.search(r"data-|chatgpt|openai|claude|anthropic|export", low):
                    if any(n.endswith("conversations.json") for n in zipfile.ZipFile(f).namelist()):
                        chats["export_candidates"].append({"path": str(f), "type": "provider export zip (conversations.json inside)",
                                                           "modified": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).date().isoformat()})
                elif f.suffix == ".json" and "conversations" in low:
                    head = f.open("rb").read(8192).decode("utf-8", "ignore")
                    kind = "claude.ai" if "chat_messages" in head else "chatgpt" if '"mapping"' in head else None
                    if kind:
                        chats["export_candidates"].append({"path": str(f), "type": f"{kind} conversations.json",
                                                           "modified": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).date().isoformat()})
            except (OSError, zipfile.BadZipFile):
                continue
    chats["cursor"] = None
    cur_dbs = [home / sub / "Cursor/User/globalStorage/state.vscdb" for sub in
               ("Library/Application Support", ".config", "AppData/Roaming")]
    cur_dbs = [d for d in cur_dbs if d.is_file()]
    cur_tr = home / ".cursor" / "projects"
    cur_tr = cur_tr if cur_tr.is_dir() and any(cur_tr.glob("*/agent-transcripts")) else None
    if cur_dbs or cur_tr:
        chats["cursor"] = {"state_db": str(cur_dbs[0]) if cur_dbs else None,
                           "agent_transcripts": str(cur_tr) if cur_tr else None,
                           "note": "pass either path to --chat; the db is copied read-only, contents are redacted"}
    gh = shutil.which("gh")
    login = None
    if gh:
        r = subprocess.run([gh, "api", "user", "-q", ".login"], capture_output=True, text=True)
        login = r.stdout.strip() if r.returncode == 0 else None
    out = {"identity": {"names_and_emails_seen": sorted(identities),
                        "suggested_me_regex": "|".join(re.escape(x) for x in sorted(identities) if "@" in x or " " in x.strip()) or None,
                        "note": "single-word names are left out of the regex on purpose (they match other authors); add them manually if needed",
                        "agent_authors_seen": sorted(agent_authors)},
           "repos": repos, "roots_scanned": [str(r) for r in roots if r.is_dir()], "chat": chats,
           "agents_installed": {k: Path(v).expanduser().exists() for k, v in AGENT_PROBE.items()},
           "tools": {"gh": bool(gh), "gh_login": login, "git": bool(shutil.which("git"))},
           "skill": {"root": str(ROOT), "upstream_origin": git(["remote", "get-url", "origin"], ROOT).strip() or None}}
    txt = json.dumps(out, indent=2)
    Path(a.out).write_text(txt) if a.out else print(txt)


def cmd_ledger(a):
    for e in load()["ledger"][-a.n:]:
        print(json.dumps(e))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("collect")
    p.add_argument("--months", type=float, default=6)
    p.add_argument("--days", type=int)
    p.add_argument("--repo", action="append", required=True)
    p.add_argument("--chat", action="append")
    p.add_argument("--me", action="append")
    p.add_argument("--agent", action="append")
    p.add_argument("--scan-secrets", action="store_true")
    p.add_argument("--prs", action="store_true")
    p.add_argument("--risky-regex")
    p.add_argument("--god-loc", type=int, default=800)
    p.set_defaults(f=cmd_collect)
    p = sp.add_parser("suggest-gaps")
    p.add_argument("--evidence")
    p.add_argument("--json", action="store_true")
    p.set_defaults(f=cmd_suggest)
    p = sp.add_parser("import")
    p.add_argument("evaluation")
    p.add_argument("--evidence")
    p.add_argument("--report", help="markdown report to register (copied to ~/.senior-coach/reports)")
    p.add_argument("--mode", choices=["escalate", "nudge", "gate", "off"], help="default: nudge, auto-escalating after 7 days")
    p.set_defaults(f=cmd_import)
    p = sp.add_parser("discover")
    p.add_argument("--root", action="append")
    p.add_argument("--out")
    p.set_defaults(f=cmd_discover)
    p = sp.add_parser("init")
    p.add_argument("--agent", action="append", choices=list(AGENT_DIRS))
    p.add_argument("--relink", action="store_true")
    p.set_defaults(f=cmd_init)
    p = sp.add_parser("report")
    p.add_argument("--save")
    p.set_defaults(f=cmd_report)
    p = sp.add_parser("integrate")
    p.add_argument("--agent", required=True, choices=["claude-code", "cursor", "agents-md"])
    p.add_argument("--repo", action="append")
    p.add_argument("--settings")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(f=cmd_integrate)
    p = sp.add_parser("install-ci")
    p.add_argument("--repo", action="append")
    p.add_argument("--owner")
    p.add_argument("--force", action="store_true")
    p.set_defaults(f=cmd_install_ci)
    p = sp.add_parser("set-owner")
    p.add_argument("owner")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(f=cmd_set_owner)
    p = sp.add_parser("module")
    p.add_argument("gap")
    p.set_defaults(f=cmd_module)
    sp.add_parser("status").set_defaults(f=cmd_status)
    sp.add_parser("next").set_defaults(f=cmd_next)
    p = sp.add_parser("task")
    p.add_argument("gap")
    p.add_argument("task")
    p.add_argument("action", choices=["start", "done", "review"])
    p.add_argument("--note")
    p.set_defaults(f=cmd_task)
    p = sp.add_parser("verify")
    p.add_argument("gap", nargs="?")
    p.add_argument("--chat")
    p.set_defaults(f=cmd_verify)
    p = sp.add_parser("check")
    p.add_argument("--event", required=True, choices=["commit-msg", "pre-commit", "pre-push", "agent-done", "prompt", "ci"])
    p.add_argument("--msg-file")
    p.add_argument("--base")
    p.add_argument("--text")
    p.add_argument("--stdin-json", action="store_true")
    p.add_argument("--stateless", action="store_true", help="CI mode: all library gaps active, no state")
    p.add_argument("--out", choices=["stderr", "stdout"], default="stderr")
    p.add_argument("--audience", choices=["human", "agent"], default="human")
    p.add_argument("--block-exit", type=int, default=1)
    p.set_defaults(f=cmd_check)
    p = sp.add_parser("note")
    p.add_argument("--kind", default="blast-radius")
    p.add_argument("--text", required=True)
    p.set_defaults(f=cmd_note)
    p = sp.add_parser("install-hooks")
    p.add_argument("--repo", action="append")
    p.set_defaults(f=cmd_install)
    p = sp.add_parser("ledger")
    p.add_argument("-n", type=int, default=20)
    p.set_defaults(f=cmd_ledger)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
