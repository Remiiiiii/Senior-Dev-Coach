# Learning techniques (how the agent hosts a module)

Each plan task names a technique (see `techniques` in `gap-library.json`). The technique decides **how you teach**; the task kind (`metric | attest | quiz`) decides **how completion is verified**. Always run it on the developer's own code, commits and prompts, never a textbook example, and make them attempt before you show anything.

The number and mix of lessons is not fixed. `coach.py import` selects library tasks from the evaluation evidence and adds the agent-authored `custom_tasks` you put in `evaluation.json`. When you write the evaluation, choose techniques by **how the gap closes**:

| The gap is mostly... | Reach for | Why |
|---|---|---|
| Not knowing a concept or rule of thumb | retrieval-quiz, then spaced re-tests | Recall under no-AI conditions is what transfers to live work |
| Not having done the skill before | worked-example (faded), then live-pairing | Seeing one done, then doing yours, beats lectures |
| A habit that decays under deadline | deliberate-kata, if-then-plan | Repetition with feedback, plus a trigger the hooks will supply |
| Structure/architecture on a real file | guided-refactor, design-note | Change real code in small safe steps; write down the decision |
| Spotting risk in diffs, routes, plans | review-drill | Finding planted or real flaws trains the review eye |
| Cause-finding | debug-lab | Forces the hypothesis loop before touching code |
| Owning code you did not type | explain-back | If you cannot explain it without the chat, you do not own it |
| Process that fails repeatedly | pre-mortem | Convert likely failures into checks |
| Vague communication (commits, prompts, tickets) | rewrite-artifact | Before/after on their own text is concrete |
| Something git or chat can measure | metric-challenge | Automatic, honest verification |

Custom lessons should cite the evidence they come from (`evidence_ref`: a commit hash, file, or redacted chat excerpt). Prefer 1-3 sharp custom lessons per gap over many generic ones. Scale the total to the developer's time budget: roughly 1 task per week per active gap.

## Playbooks

**retrieval-quiz** (quiz, spaced). 1) <= 150-word lesson using their code. 2) Ask 3 questions that test judgment ("which of these two commits could you revert safely, and why?"). 3) No hints before an answer. 4) Pass = 2/3 unaided, third corrected in their own words. Record `passed 2/3 on <topic>`. Reviews come at +3, +10, +30 days: re-ask a *different* question on the same idea.

**worked-example** (attest). 1) You do the task on a different case, narrating decisions. 2) Hand over a similar case with half the steps blanked. 3) They do their own real case; you only answer questions. Evidence: their commit/artifact.

**guided-refactor** (attest). They drive, you navigate by asking: "what does this function own? what would you move first? what test pins it?". No big-bang rewrites; each step green. Evidence: commit range with tests unchanged.

**deliberate-kata** (attest, spaced). A small drill done 3 times, each round with specific feedback and a harder constraint (e.g. rewrite 10 commit subjects; then 10 more under a 50-character limit; then from diffs alone). Evidence: the three rounds.

**review-drill** (quiz, spaced). Pick a real diff/route from their history, or plant 3-5 flaws in a short synthetic one. They find them without AI; you score found / false alarms. Pass = >= 70% of flaws, <= 1 false alarm. Debrief every miss.

**debug-lab** (quiz, spaced). Give a bug report (real past bug or a seeded one). They write ranked hypotheses and the cheapest experiment for each *before* any code. Score the loop, not the speed. Evidence: the written loop and the regression test.

**explain-back** (quiz, spaced). Choose a large change they own (often AI-authored). With no AI or chat open they explain: what it does, where it can break, how to roll back. Grade on the rubric: accuracy, failure modes, rollback. Fail = re-read together, retry in a few days with a different change.

**pre-mortem** (attest). "It is 3 months later and this failed. Why?" List 5-8 causes, rank by likelihood x cost, turn the top 3 into checks (CI step, PR checklist item, hook). Evidence: the checks, merged.

**if-then-plan** (attest). They write 2-3 rules like "if I stage > 15 files, then I split by concern before committing". The git/agent hooks provide the trigger; you refer to the rule when a finding fires. Evidence: the written rules; reviewed at the next `status`.

**rewrite-artifact** (attest). Take 3 real artifacts (commit subjects, prompts, ticket text). They rewrite them to the target form; compare side by side. Evidence: before/after.

**design-note** (attest). One page: context, 2 options, decision, consequences, rollback. Keep it in the repo's docs folder if the team agrees. Evidence: the note.

**live-pairing** (attest). A real backlog item done under constraints you enforce during the work (file allowlist, tests first, PR <= 400 lines). Evidence: PR/commit range.

**metric-challenge** (metric). State the target and the minimum sample. They do normal work; `coach.py verify` confirms. Never mark it done yourself.

## Quality bar for any lesson

- Starts from their evidence; ends in a change to their real work.
- Attempt before answer; feedback is specific ("this subject says what, not why").
- Short: one idea, 10-20 minutes.
- Honest grading. A fail with a clear next step is more useful than a generous pass.
- Evidence standards: see `module-spec.md`.
