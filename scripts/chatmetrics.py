#!/usr/bin/env python3
"""Turn AI chat exports into (a) habit metrics and (b) a redacted, stratified sample of YOUR messages.

Supported inputs (file or directory, recursive):
  * Claude.ai export  conversations.json   (chat_messages[].sender/text/created_at)
  * ChatGPT export    conversations.json   (mapping{} nodes with author.role/create_time)
  * JSONL transcripts (Claude Code / Cursor-style: one JSON object per line with role|type + message|content)
  * .zip              (Claude.ai / ChatGPT export archives containing conversations.json)
  * Cursor            state.vscdb (SQLite; read-only copy): globalStorage cursorDiskKV rows
                      composerData:<id> + bubbleId:<id>:<bubble> (type 1 = you, 2 = assistant), plus the
                      legacy workspace ItemTable keys. Also ~/.cursor/projects/*/agent-transcripts/ (.jsonl/.txt)
  * .md / .txt        (role markers like "User:", "**You:**", "## Human"); file mtime used as timestamp

Everything runs locally. Output contains only redacted excerpts, never full transcripts.
"""
import argparse
import json
import re
import statistics as st
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patterns as P  # noqa: E402

REDACT = [
    ("secret", re.compile("|".join(rx.pattern for _, rx in P.SECRET_PATTERNS[:5]))),
    ("credential", P.SECRET_PATTERNS[5][1]),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("token", re.compile(r"\b[A-Za-z0-9+/_-]{32,}={0,2}\b")),
    ("ip", re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b")),
    ("home", re.compile(r"/(Users|home)/[^/\s]+")),
]

W = lambda s: re.compile(s, re.I)  # noqa: E731
CONSTRAINT = W(r"\b(must|should(n't| not)?|must not|don'?t|do not|only|without|non-?goals?|acceptance|"
               r"expected|requirements?|constraints?|at most|at least|ensure|so that|out of scope)\b")
TESTWORD = W(r"\b(tests?|specs?|coverage|assert|regression)\b")
WHY = W(r"\b(why|trade-?offs?|alternatives?|pros and cons|compare|options|downsides?|risks?)\b")
VERIFY = W(r"(are you sure|did you run|double-?check|prove|walk me through|what could break|verify|"
           r"explain (why|how))")
SCOPE = W(r"(don'?t change|do not change|only touch|leave .{1,30} alone|scope|non-?goal|out of scope)")
ERRPASTE = re.compile(r"(Traceback|\bError:|TypeError|ReferenceError|Exception|ERR!|\bat .+\(.+:\d+)")
HYPO = W(r"\b(because|i think|suspect|probably|hypothesis|tried|expected|instead|maybe)\b")
IMPERATIVE = W(r"^(fix|make|add|do|build|create|update|improve|continue|implement|change|just|write)\b")
PATHLIKE = re.compile(r"(`[^`]+`|[\w-]+/[\w./-]+|\b[\w-]+\.(ts|tsx|js|py|go|rs|java|md|json)\b)")
STOP = set("this that with from have what when your there which would could should about into then them "
           "they will just like make need want also some more than only because please thanks using".split())


def redact(text, counts):
    for name, rx in REDACT:
        text, n = rx.subn(f"[{name}]", text)
        counts[name] = counts.get(name, 0) + n
    return text


def _ts(v, fallback):
    if v is None:
        return fallback
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return fallback


def _text(v):
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "\n".join(_text(x) for x in v)
    if isinstance(v, dict):
        return _text(v.get("text") or v.get("content") or v.get("parts") or "")
    return ""


def _role(r):
    r = str(r or "").lower()
    return "user" if r in ("user", "human", "you") else ("assistant" if r in ("assistant", "ai", "claude", "model") else r)


def parse_json(data, mtime):
    convs = data if isinstance(data, list) else data.get("conversations", [data])
    for ci, conv in enumerate(convs):
        cid = conv.get("uuid") or conv.get("id") or conv.get("conversation_id") or str(ci)
        if "chat_messages" in conv:  # Claude.ai
            for m in conv["chat_messages"]:
                yield cid, _role(m.get("sender")), _ts(m.get("created_at"), mtime), _text(m.get("text") or m.get("content"))
        elif "mapping" in conv:  # ChatGPT
            for node in conv["mapping"].values():
                m = node.get("message")
                if m:
                    yield cid, _role(m["author"]["role"]), _ts(m.get("create_time"), mtime), _text(m.get("content"))
        elif "messages" in conv:
            for m in conv["messages"]:
                yield cid, _role(m.get("role")), _ts(m.get("timestamp") or m.get("created_at"), mtime), _text(m.get("content"))


def parse_jsonl_text(text, stem, mtime):
    for line in text.splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        msg = o.get("message") if isinstance(o.get("message"), dict) else o
        role = _role(msg.get("role") or o.get("role") or o.get("type"))
        yield stem, role, _ts(o.get("timestamp") or o.get("created_at"), mtime), _cursor_text(_text(msg.get("content") or o.get("content")))


def parse_jsonl(path, mtime):
    yield from parse_jsonl_text(path.read_text(errors="replace"), path.stem, mtime)


def parse_zip(path, mtime):
    """Provider exports (Claude.ai, ChatGPT) are zips containing conversations.json."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith("conversations.json") and z.getinfo(name).file_size < 500_000_000:
                yield from parse_json(json.loads(z.read(name).decode("utf-8", "replace")), mtime)
            elif name.endswith(".jsonl"):
                yield from parse_jsonl_text(z.read(name).decode("utf-8", "replace"), Path(name).stem, mtime)


def parse_text(path, mtime):
    rx = re.compile(r"^\s*(?:#+\s*|\*\*)?(user|human|you|assistant|claude|ai)(?:\*\*)?\s*:?\s*\**\s*$|"
                    r"^\s*\*{0,2}(user|human|you|assistant|claude|ai):\*{0,2}\s*(.*)$", re.I)
    role, buf = None, []
    for line in path.read_text(errors="replace").splitlines():
        m = rx.match(line)
        if m:
            if role and buf:
                yield path.stem, _role(role), mtime, "\n".join(buf).strip()
            role, buf = m.group(1) or m.group(2), ([m.group(3)] if m.group(3) else [])
        else:
            buf.append(line)
    if role and buf:
        yield path.stem, _role(role), mtime, "\n".join(buf).strip()


UQ = re.compile(r"</?user_query>|</?attached_files>", re.I)


def _cursor_text(t):
    m = re.search(r"<user_query>(.*?)</user_query>", t, re.S | re.I)
    return (m.group(1) if m else UQ.sub("", t)).strip()


def parse_cursor_db(path, mtime):
    """Cursor state.vscdb. Opened on a temp copy because Cursor keeps the live DB locked/in WAL."""
    import shutil
    import sqlite3
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "s.vscdb"
        shutil.copy2(path, dst)
        for ext in ("-wal", "-shm"):
            side = Path(str(path) + ext)
            if side.exists():
                shutil.copy2(side, str(dst) + ext)
        con = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
        con.text_factory = lambda b: b.decode("utf-8", "replace")
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "cursorDiskKV" in tables:  # global store: one row per message ("bubble")
                created = {}
                for k, v in con.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"):
                    try:
                        created[k.split(":", 1)[1]] = json.loads(v).get("createdAt")
                    except (ValueError, AttributeError):
                        pass
                for k, v in con.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'"):
                    try:
                        _, cid, _bid = k.split(":", 2)
                        b = json.loads(v)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(b, dict) or b.get("type") not in (1, 2):
                        continue
                    ts = _ts(b.get("createdAt") or created.get(cid), mtime)
                    yield cid, ("user" if b["type"] == 1 else "assistant"), ts, _cursor_text(b.get("text") or "")
            if "ItemTable" in tables:  # per-workspace store: legacy chat tabs, new-format user prompts
                for k, v in con.execute("SELECT key, value FROM ItemTable WHERE key IN "
                                        "('workbench.panel.aichat.view.aichat.chatdata','composer.composerData')"):
                    try:
                        d = json.loads(v)
                    except ValueError:
                        continue
                    for tab in d.get("tabs", []):  # legacy
                        for b in tab.get("bubbles", []):
                            yield (tab.get("tabId", "tab"), "user" if b.get("type") == "user" else "assistant",
                                   _ts(b.get("timestamp") or tab.get("lastSendTime"), mtime), _cursor_text(b.get("text") or ""))
                    for c in d.get("allComposers", []):  # headers only; bodies live in the global DB
                        for b in c.get("conversation", []) or []:
                            if b.get("type") == 1 and b.get("text"):
                                yield (c.get("composerId", "c"), "user",
                                       _ts(b.get("createdAt") or c.get("createdAt"), mtime), _cursor_text(b["text"]))
        except sqlite3.Error:
            return
        finally:
            con.close()


def iter_messages(paths):
    files = []
    for p in map(Path, paths):
        p = p.expanduser()
        files += [f for f in p.rglob("*") if f.suffix in (".json", ".jsonl", ".md", ".txt", ".zip", ".vscdb")] if p.is_dir() else [p]
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        try:
            if f.suffix == ".json":
                yield from parse_json(json.loads(f.read_text(errors="replace")), mtime)
            elif f.suffix == ".jsonl":
                yield from parse_jsonl(f, mtime)
            elif f.suffix == ".zip":
                yield from parse_zip(f, mtime)
            elif f.suffix == ".vscdb":
                yield from parse_cursor_db(f, mtime)
            else:
                yield from parse_text(f, mtime)
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError, OSError, ValueError):
            continue


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def collect(paths, since, sample_per_month=6, excerpt_chars=500):
    counts, msgs, convs = {}, [], set()
    for cid, role, ts, text in iter_messages(paths):
        if role == "user" and text.strip() and ts >= since:
            msgs.append((ts, cid, text.strip()))
            convs.add(cid)
    msgs.sort(key=lambda x: x[0])
    if not msgs:
        return {"available": False, "note": "no user messages found inside the window (check path/format/dates)"}

    def prose(t):  # strip code fences / pasted logs so length reflects what the human wrote
        return re.sub(r"```.*?```", " ", t, flags=re.S)

    words = [len(prose(t).split()) for _, _, t in msgs]
    long_ = [t for (_, _, t), w in zip(msgs, words) if w >= 15]
    errs = [t for _, _, t in msgs if ERRPASTE.search(t)]
    err_nohyp = [t for t in errs if len(prose(t).split()) < 30 and not HYPO.search(prose(t))]
    vague = [t for (_, _, t), w in zip(msgs, words) if w <= 12 and IMPERATIVE.match(t) and not PATHLIKE.search(t)]
    kw = Counter(w for _, _, t in msgs for w in re.findall(r"[a-z]{4,}", prose(t).lower()) if w not in STOP)
    files = Counter()
    for cid in convs:
        seen = {m.group(0) for _, c, t in msgs if c == cid for m in PATHLIKE.finditer(t) if "/" in m.group(0) or "." in m.group(0)}
        files.update(seen)
    by_month = {}
    for ts, cid, t in msgs:
        by_month.setdefault(ts.strftime("%Y-%m"), []).append((ts, cid, t))
    sample = []
    for month, items in sorted(by_month.items()):
        cand = [x for x in items if len(x[2].split()) >= 8]
        pick = [cand[int(i * len(cand) / sample_per_month)] for i in range(min(sample_per_month, len(cand)))] if cand else []
        for ts, cid, t in pick:
            tags = [n for n, rx in (("error-paste", ERRPASTE), ("constraints", CONSTRAINT), ("asks-why", WHY)) if rx.search(t)]
            sample.append({"month": month, "conversation": str(cid)[:12], "tags": tags,
                           "text": redact(t[:excerpt_chars], counts)})
    n, nl = len(msgs), len(long_)
    return {
        "available": True, "conversations": len(convs), "user_messages": n,
        "median_user_words": st.median(words),
        "constraint_pct": _pct(sum(1 for t in long_ if CONSTRAINT.search(t)), nl),
        "test_mention_pct": _pct(sum(1 for t in long_ if TESTWORD.search(t)), nl),
        "why_tradeoff_pct": _pct(sum(1 for t in long_ if WHY.search(t)), nl),
        "verification_pct": _pct(sum(1 for _, _, t in msgs if VERIFY.search(t)), n),
        "scope_control_pct": _pct(sum(1 for _, _, t in msgs if SCOPE.search(t)), n),
        "vague_prompt_pct": _pct(len(vague), n),
        "error_paste_pct": _pct(len(errs), n),
        "error_paste_no_hypothesis_pct": _pct(len(err_nohyp), len(errs)),
        "top_keywords": [k for k, _ in kw.most_common(15)],
        "recurring_files": [f for f, c in files.most_common(10) if c >= 3],
        "messages_per_month": {m: len(v) for m, v in sorted(by_month.items())},
        "redactions": counts,
        "sample": sample,
        "caveat": "Percentages are keyword heuristics. Read the sample before concluding anything.",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chat", action="append", required=True)
    ap.add_argument("--months", type=float, default=6)
    ap.add_argument("--out")
    a = ap.parse_args()
    from datetime import timedelta
    res = collect(a.chat, datetime.now(timezone.utc) - timedelta(days=round(a.months * 30.4375)))
    txt = json.dumps(res, indent=2)
    Path(a.out).write_text(txt) if a.out else print(txt)


if __name__ == "__main__":
    main()
