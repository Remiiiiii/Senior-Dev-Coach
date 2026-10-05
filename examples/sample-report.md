# Senior-level evaluation: sample (synthetic data)

**Window:** 6 months | **Repos:** `shop-api` | **Chat corpus:** 41 conversations (confidence: medium)
**Not assessed:** review quality from teammates, production incidents, design without AI

## 1. Executive summary
Ships a lot: 310 commits, 22% agent-authored, steady monthly growth. Output is mid-to-senior; the blocker is control of change size and AI output ownership: median 24 files per commit, 68% vague subjects, two PRs over 4k lines. Security instincts (authz rules, deny tests on new routes) are above mid. **Verdict: solid mid / senior-leaning.**

## 2. Scorecard (excerpt)
| Dimension | Score | Confidence | Evidence |
|---|---|---|---|
| git_process | 2 | high | median 24 files/commit; conventional 14%; commits over 40 files: 12% |
| testing | 2.5 | high | test colocation 41% of source commits; risky-without-test 55% |
| security | 3.5 | high | authz matrix + rules file; one credential in history (commit `a1b2c3d`) |
| requirements | 4 | medium | chat sample: acceptance criteria and non-goals in most feature asks |

## 3. Facts vs inferences
- **Fact:** 4 files over 800 lines, the largest 2,900 lines, also the top churn file.
- **Inference (mine):** the habit is shipping surface area over bounding blast radius; chat shows "fix it" follow-ups right after large agent diffs.
- **Could not assess:** whether you can explain the largest agent PR without the chat open.

## 5. Improvement plan (excerpt: gap 1)
- **Senior looks like:** one concern per PR, commits that say why, green CI before "done".
- **Exercises:** split the 2,900-line file's date helpers into their own module in a no-behavior-change PR; rewrite your last 10 vague subjects; cap agent changes at 40 files.
- **Success signals (30d):** median files/commit <= 12; conventional >= 60%.

## 6. If you only do three things
1. Cap blast radius: no unmarked 100-file PRs. 2. Ship deny + wrong-scope tests with every permission change. 3. Treat AI output like a junior's PR: allowed files, required tests, a blast-radius note.
