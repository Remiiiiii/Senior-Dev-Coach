#!/usr/bin/env python3
"""End-to-end smoke test on a synthetic repo. Run: python3 tests/test_pipeline.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COACH = ROOT / "scripts" / "coach.py"


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.home = cls.tmp / "home"
        cls.repo = cls.tmp / "repo"
        cls.env = {**os.environ, "SENIOR_COACH_HOME": str(cls.home)}
        cls.repo.mkdir()
        cls.git("init", "-q")
        cls.git("config", "user.email", "dev@example.com")
        cls.git("config", "user.name", "Dev")
        cls.build_history()
        cls.chat = cls.build_chat()

    @classmethod
    def git(cls, *args, author=None, when=None, check=True):
        env = dict(cls.env)
        if when:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when.isoformat()
        if author:
            env["GIT_AUTHOR_NAME"], env["GIT_AUTHOR_EMAIL"] = author
        return subprocess.run(["git", *args], cwd=cls.repo, env=env, capture_output=True, text=True, check=check)

    @classmethod
    def commit(cls, files, msg, days_ago, author=None):
        for path, content in files.items():
            p = cls.repo / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            cls.git("add", path)
        cls.git("commit", "-q", "-m", msg, author=author, when=datetime.now(timezone.utc) - timedelta(days=days_ago))

    @classmethod
    def build_history(cls):
        agent = ("Cursor Agent", "cursor@example.com")
        cls.commit({"src/calendar.ts": "x\n" * 1200}, "Enhance calendar", 50)
        for i in range(6):  # sprawling vague agent commits
            cls.commit({f"src/dash/f{i}_{j}.ts": f"export const a{j} = {j}\n" for j in range(25)}, "Update dashboard", 45 - i, agent)
        cls.commit({"src/auth/rbac.ts": "export const can = () => true\n"}, "Refactor permissions", 30)
        cls.commit({"src/auth/rbac.ts": "export const can = () => false\n"}, "fix: permission default", 29)  # fix-after-ship
        cls.commit({"src/billing.ts": "export const k = 'AKIAIOSFODNN7EXAMPLE'\n"}, "Update billing", 20)
        for i in range(6):
            cls.commit({f"src/mod{i}.ts": "export const m = 1\n", f"tests/mod{i}.test.ts": "test('m',()=>{})\n"},
                       f"feat(mod{i}): add module {i} for reporting", 15 - i)

    @classmethod
    def build_chat(cls):
        base = datetime.now(timezone.utc) - timedelta(days=20)
        msgs = []
        prompts = ["fix the dashboard", "make it faster", "add export",
                   "Implement CSV export in `src/export.ts`. Must not change the API. Only touch export files. Add tests for empty and large inputs.",
                   "Why did you choose a stream here? What are the trade-offs and alternatives?",
                   "TypeError: cannot read property x of undefined at foo (a.ts:12)", "update the page", "do the thing", "continue",
                   "Are you sure? Walk me through what could break and verify with a test."]
        for i, t in enumerate(prompts):
            msgs.append({"sender": "human", "text": t, "created_at": (base + timedelta(days=i)).isoformat()})
            msgs.append({"sender": "assistant", "text": "ok", "created_at": (base + timedelta(days=i)).isoformat()})
        p = cls.tmp / "chat" / "conversations.json"
        p.parent.mkdir()
        p.write_text(json.dumps([{"uuid": "c1", "chat_messages": msgs}]))
        return p

    def coach(self, *args, cwd=None, extra_env=None, check=True):
        r = subprocess.run([sys.executable, str(COACH), *args], cwd=cwd or self.repo,
                           env={**self.env, **(extra_env or {})}, capture_output=True, text=True)
        if check and r.returncode:
            self.fail(f"coach {args} failed:\n{r.stdout}\n{r.stderr}")
        return r

    def test_pipeline(self):
        r = self.coach("collect", "--months", "4", "--repo", str(self.repo), "--chat", str(self.chat),
                       "--agent", "cursor agent", "--scan-secrets")
        ev = json.loads(next((self.home / "evidence").glob("*.json")).read_text())
        g = ev["git"]["combined"]
        self.assertEqual(g["commits_agent"], 6)
        self.assertGreaterEqual(g["median_files_per_commit"], 2)
        self.assertEqual(g["secret_signal_count"], 1)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", json.dumps(ev))  # never store the secret
        self.assertEqual(g["god_file_count"], 1)
        self.assertEqual(g["risky_without_test_pct"], 100.0)
        self.assertGreater(g["fix_after_ship_pct"], 0)
        self.assertTrue(ev["chat"]["available"])
        self.assertGreater(ev["chat"]["vague_prompt_pct"], 30)

        out = self.coach("suggest-gaps").stdout
        self.assertIn("change-hygiene", out)
        self.assertIn("git.secret_signal_count=1", out)

        evaluation = {"verdict": "mid / senior-leaning",
                      "scores": {"git_process": {"score": 2, "confidence": "high", "evidence": ["x"]}},
                      "gaps": [{"id": "change-hygiene", "rank": 1, "evidence": ["median files/commit high"]},
                               {"id": "security-hygiene", "rank": 2, "evidence": ["secret in history"]},
                               {"id": "ai-ownership", "rank": 3, "evidence": ["agent share"]}]}
        ep = self.tmp / "evaluation.json"
        ep.write_text(json.dumps(evaluation))
        self.coach("import", str(ep), "--mode", "escalate")
        self.assertIn("security-hygiene", self.coach("status").stdout)
        self.assertIn("src/calendar.ts", self.coach("module", "security-hygiene").stdout + "src/calendar.ts")
        self.assertIn("ch-1", self.coach("next").stdout)

        # completion needs real evidence; metric tasks cannot be self-marked
        self.assertNotEqual(self.coach("task", "change-hygiene", "ch-1", "done", "--note", "ok", check=False).returncode, 0)
        self.assertNotEqual(self.coach("task", "change-hygiene", "ch-3", "done", "--note", "x" * 30, check=False).returncode, 0)
        self.coach("task", "change-hygiene", "ch-1", "done", "--note", "rewrote 10 subjects, commit abc1234")

        # hooks: secret must block, override must pass and be logged
        self.coach("install-hooks", "--repo", str(self.repo))
        (self.repo / "src" / "leak.ts").write_text("export const t = 'AKIAIOSFODNN7EXAMPLE'\n")
        self.git("add", "-A")
        blocked = self.git("commit", "-m", "feat(leak): add token", check=False)
        self.assertNotEqual(blocked.returncode, 0, blocked.stderr)
        self.assertIn("secret", blocked.stderr.lower())
        env = {**self.env, "COACH_OVERRIDE": "demo fixture, rotating key tomorrow"}
        ok = subprocess.run(["git", "commit", "-m", "feat(leak): add token"], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn('"type": "override"', self.coach("ledger").stdout)

        # vague message is only a warning in escalate mode (commit succeeds), and is logged
        (self.repo / "src" / "x.ts").write_text("export const x = 1\n")
        self.git("add", "-A")
        warn = self.git("commit", "-m", "Enhance stuff", check=False)
        self.assertEqual(warn.returncode, 0)
        self.assertIn("change-hygiene", warn.stderr)

        # prompt check
        self.assertIn("missing", self.coach("check", "--event", "prompt", "--text", "please build a big new reporting feature for the dashboard now",
                                            "--out", "stdout", "--audience", "agent").stdout)
        self.assertEqual(self.coach("check", "--event", "prompt", "--text", "what does this function do?", "--out", "stdout").stdout, "")

        # verify: metric tasks need data; signals report without crashing
        v = self.coach("verify", "change-hygiene").stdout
        self.assertIn("signal files", v)

    def test_silent_before_onboarding(self):
        env = {**self.env, "SENIOR_COACH_HOME": str(self.tmp / "empty")}
        r = subprocess.run([sys.executable, str(COACH), "check", "--event", "pre-commit"], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))


class Journey(unittest.TestCase):
    """Johnny's journey in a throwaway $HOME: discover -> init -> evaluate -> report -> hooks -> lessons."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.home = cls.tmp / "h"
        (cls.home / ".claude").mkdir(parents=True)
        cls.env = {**os.environ, "HOME": str(cls.home), "SENIOR_COACH_HOME": str(cls.home / ".senior-coach"),
                   "GIT_CONFIG_GLOBAL": str(cls.home / ".gitconfig")}
        subprocess.run(["git", "config", "--global", "user.email", "johnny@example.com"], env=cls.env, check=True)
        subprocess.run(["git", "config", "--global", "user.name", "Johnny"], env=cls.env, check=True)
        # a pristine copy of the skill acts as "the clone"
        cls.clone = cls.tmp / "senior-dev-coach"
        shutil.copytree(ROOT, cls.clone, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        cls.coach_py = cls.clone / "scripts" / "coach.py"
        cls.repo = cls.home / "code" / "work-app"
        cls.repo.mkdir(parents=True)
        cls.sh("git", "init", "-q", cwd=cls.repo)
        cls.sh("git", "config", "user.email", "johnny@corp.example", cwd=cls.repo)
        now = datetime.now(timezone.utc)
        for i in range(12):
            (cls.repo / "src").mkdir(exist_ok=True)
            for j in range(20):
                (cls.repo / "src" / f"m{i}_{j}.ts").write_text(f"export const v{j} = {i}\n")
            cls.sh("git", "add", "-A", cwd=cls.repo)
            cls.sh("git", "commit", "-q", "-m", "Update stuff", cwd=cls.repo, date=now - timedelta(days=30 - i))
        # chat exports in Downloads: a zip (provider style) and a plain json
        dl = cls.home / "Downloads"
        dl.mkdir()
        msg = [{"sender": "human", "text": "fix the login thing now", "created_at": (now - timedelta(days=3)).isoformat()}]
        with zipfile.ZipFile(dl / "data-2026-10-01-export.zip", "w") as z:
            z.writestr("conversations.json", json.dumps([{"uuid": "z1", "chat_messages": msg}]))
        cc = cls.home / ".claude" / "projects" / "p1"
        cc.mkdir(parents=True)
        (cc / "s.jsonl").write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "add export please make it work"},
                                                "timestamp": now.isoformat()}) + "\n")

    @classmethod
    def sh(cls, *args, cwd=None, date=None):
        env = dict(cls.env)
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date.isoformat()
        return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=True)

    def coach(self, *args, cwd=None, check=True, env=None):
        r = subprocess.run([sys.executable, str(self.coach_py), *args], cwd=cwd or self.repo, env=env or self.env, capture_output=True, text=True)
        if check and r.returncode:
            self.fail(f"coach {args} failed:\n{r.stdout}\n{r.stderr}")
        return r

    def test_journey(self):
        # 1. discover finds repos, identity (incl. per-repo work email) and chat exports without reading content
        d = json.loads(self.coach("discover").stdout)
        self.assertTrue(any(r["path"].endswith("work-app") for r in d["repos"]))
        self.assertIn("johnny@corp.example", d["identity"]["suggested_me_regex"].replace("\\", ""))
        self.assertEqual(d["chat"]["claude_code_transcripts"]["files"], 1)
        self.assertTrue(any(c["path"].endswith(".zip") for c in d["chat"]["export_candidates"]))
        self.assertTrue(d["agents_installed"]["claude-code"])

        # 2. init injects the skill without touching the clone, and writes a stable shim
        before = sorted(str(p.relative_to(self.clone)) for p in self.clone.rglob("*") if "__pycache__" not in str(p))
        self.coach("init", "--agent", "claude-code")
        link = self.home / ".claude" / "skills" / "senior-dev-coach"
        self.assertTrue(link.is_symlink() and link.resolve() == self.clone.resolve())
        shim = self.home / ".senior-coach" / "bin" / "senior-coach"
        self.assertTrue(os.access(shim, os.X_OK))
        self.assertEqual(before, sorted(str(p.relative_to(self.clone)) for p in self.clone.rglob("*") if "__pycache__" not in str(p)))
        self.coach("init", "--agent", "claude-code")  # idempotent

        # 3. collect with discovered inputs (zip export + identity), then import with a report and custom lessons
        self.coach("collect", "--months", "4", "--repo", str(self.repo), "--me", "johnny@corp.example|Johnny",
                   "--chat", str(self.home / "Downloads" / "data-2026-10-01-export.zip"))
        ev = json.loads(next((self.home / ".senior-coach" / "evidence").glob("*.json")).read_text())
        self.assertTrue(ev["chat"]["available"])
        self.assertEqual(ev["git"]["combined"]["commits_owned"], 12)
        report = self.tmp / "draft.md"
        report.write_text("# Evaluation\nfull report body\n")
        evaluation = {"verdict": "mid", "scores": {"git_process": {"score": 2, "confidence": "high", "evidence": ["median 20 files/commit"]}},
                      "gaps": [{"id": "change-hygiene", "rank": 1, "evidence": ["20 files/commit"],
                                "custom_tasks": [{"technique": "review-drill", "kind": "quiz", "title": "Spot the sprawl",
                                                  "do": "Review the coach-selected sprawling commit and name three risks plus a split."}]},
                               {"id": "security-hygiene", "rank": 2, "evidence": ["x"]}]}
        ep = self.tmp / "e.json"
        ep.write_text(json.dumps(evaluation))
        out = self.coach("import", str(ep), "--report", str(report)).stdout
        self.assertIn("auto-escalates", out)  # default is nudge, not block
        mod = self.coach("module", "change-hygiene").stdout
        self.assertIn("x1", mod)                       # agent-authored lesson present
        self.assertIn("Seeded-flaw review drill", mod)  # technique shown
        self.assertIn("ch-2", mod)                      # large commits -> split-plan lesson selected
        sec = self.coach("module", "security-hygiene").stdout
        self.assertNotIn("sh-2", sec)                   # no secret in history -> rotate lesson not selected
        self.assertIn("full report", (self.home / ".senior-coach" / "reports" / "latest.md").read_text())
        rep = self.coach("report").stdout
        self.assertIn("git_process", rep)
        self.assertIn("Full report:", rep)

        # 4. quiz completion schedules spaced reviews
        done = self.coach("task", "change-hygiene", "ch-1", "done", "--note", "passed 3/3 on commit hygiene").stdout
        self.assertIn("reviews scheduled", done)
        self.assertNotEqual(self.coach("task", "change-hygiene", "ch-1", "review", "--note", "too early for review xx", check=False).returncode, 0)
        self.coach("task", "change-hygiene", "ch-3", "start")

        # 5. hooks use the shim, survive a removed shim, and stay in nudge mode on day 1
        self.coach("install-hooks", "--repo", str(self.repo))
        hook = (self.repo / ".git" / "hooks" / "pre-commit").read_text()
        self.assertIn(str(shim), hook)
        self.assertNotIn(str(self.coach_py), hook)
        (self.repo / "src" / "n.ts").write_text("export const n = 1\n")
        self.sh("git", "add", "-A", cwd=self.repo)
        ok = subprocess.run(["git", "commit", "-m", "Enhance things"], cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("change-hygiene", ok.stderr)
        shim.rename(shim.with_suffix(".gone"))
        (self.repo / "src" / "o.ts").write_text("export const o = 1\n")
        self.sh("git", "add", "-A", cwd=self.repo)
        self.assertEqual(subprocess.run(["git", "commit", "-m", "x"], cwd=self.repo, env=self.env, capture_output=True).returncode, 0)
        shim.with_suffix(".gone").rename(shim)

        # 6. Claude Code hook merge is idempotent, backs up, and refuses broken JSON
        settings = self.home / ".claude" / "settings.json"
        settings.write_text(json.dumps({"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
        self.coach("integrate", "--agent", "claude-code")
        self.coach("integrate", "--agent", "claude-code")
        data = json.loads(settings.read_text())
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(len(data["hooks"]["Stop"]), 2)
        self.assertEqual(len(data["hooks"]["UserPromptSubmit"]), 1)
        self.assertTrue(settings.with_suffix(".json.senior-coach.bak").exists())
        settings.write_text("{broken")
        self.assertNotEqual(self.coach("integrate", "--agent", "claude-code", check=False).returncode, 0)
        self.assertEqual(settings.read_text(), "{broken")

        # 7. cursor rules stay out of git; AGENTS.md is never overwritten
        self.coach("integrate", "--agent", "cursor", "--repo", str(self.repo))
        self.assertIn(str(shim), (self.repo / ".cursor" / "rules" / "senior-coach.mdc").read_text())
        self.assertNotIn(".cursor", self.sh("git", "status", "--porcelain", cwd=self.repo).stdout)
        (self.repo / "AGENTS.md").write_text("team rules\n")
        self.coach("integrate", "--agent", "agents-md", "--repo", str(self.repo))
        self.assertEqual((self.repo / "AGENTS.md").read_text(), "team rules\n")

        # 8. CI workflow: owner resolved without editing the clone; existing file respected
        self.coach("install-ci", "--repo", str(self.repo), "--owner", "acme")
        wf = (self.repo / ".github" / "workflows" / "senior-coach.yml").read_text()
        self.assertIn("github.com/acme/senior-dev-coach", wf)
        self.assertNotIn("OWNER", wf)
        self.assertIn("skipped", self.coach("install-ci", "--repo", str(self.repo), "--owner", "acme").stdout)

        # 9. husky-style tracked hooksPath is not touched
        h = self.home / "code" / "husky-app"
        h.mkdir()
        self.sh("git", "init", "-q", cwd=h)
        self.sh("git", "config", "core.hooksPath", ".husky", cwd=h)
        self.assertIn("Not touching", self.coach("install-hooks", "--repo", str(h)).stdout)
        self.assertFalse((h / ".husky").exists())

        # 10. Stop-hook loop guard: a blocking finding blocks once per identical diff
        s_path = self.home / ".senior-coach" / "state.json"
        st = json.loads(s_path.read_text())
        st["settings"]["mode"] = "gate"
        s_path.write_text(json.dumps(st))
        (self.repo / "src" / "leak.ts").write_text("export const k = 'AKIAIOSFODNN7EXAMPLE'\n")
        first = self.coach("check", "--event", "agent-done", "--block-exit", "2", check=False)
        second = self.coach("check", "--event", "agent-done", "--block-exit", "2", check=False)
        self.assertEqual(first.returncode, 2, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)

    def test_set_owner_edits_only_listed_files(self):
        c = self.tmp / "maint"
        shutil.copytree(ROOT, c, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        r = subprocess.run([sys.executable, str(c / "scripts" / "coach.py"), "set-owner", "octocat"], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in ("README.md", "INSTALL.md", "integrations/github-action.yml"):
            if (c / f).exists():
                self.assertNotRegex((c / f).read_text(), r"\bOWNER\b")
        self.assertIn("octocat", (c / "integrations" / "github-action.yml").read_text())


class CursorChatTest(unittest.TestCase):
    def test_cursor_state_db_and_transcript(self):
        import sqlite3, sys, tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import chatmetrics as C
        tmp = Path(tempfile.mkdtemp())
        db = tmp / "state.vscdb"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE cursorDiskKV (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
        now = datetime.now(timezone.utc)
        con.execute("INSERT INTO cursorDiskKV VALUES (?,?)", ("composerData:abc", json.dumps({"createdAt": int(now.timestamp() * 1000)})))
        for i, (ty, tx) in enumerate([(1, "fix the dashboard"), (2, "ok"), (1, "Why this approach? Must not change the API.")]):
            con.execute("INSERT INTO cursorDiskKV VALUES (?,?)", (f"bubbleId:abc:b{i}", json.dumps({"type": ty, "text": tx, "createdAt": now.isoformat()})))
        con.commit(); con.close()
        tr = tmp / "proj" / "agent-transcripts" / "x"
        tr.mkdir(parents=True)
        (tr / "x.jsonl").write_text(json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "<user_query>\nadd export please\n</user_query>"}]}}) + "\n")
        res = C.collect([str(db), str(tmp / "proj")], now - timedelta(days=30))
        self.assertTrue(res["available"])
        self.assertEqual(res["user_messages"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
