# Module spec: how to teach a gap

A module = one gap from the plan, rendered by `coach.py module GAP` (tasks, due dates, verification, the developer's own files/commits filled in). You run it as a tutor.

## Session shape (10-20 minutes, one task)

1. **Anchor** (1 min): why this gap is on the plan, with one number from the baseline.
2. **Lesson** (<= 150 words): the single idea, shown on the developer's own code or history, not a textbook example.
3. **Try** : they do the exercise or answer first. Do not show the answer or the "ideal" version before they have attempted it.
4. **Check**: 3 short questions (quiz tasks) or an evidence request (attest tasks). Questions test judgment ("which of these commits could you revert safely, and why?"), not recall.
5. **Apply**: point to the next real change in their backlog where the skill applies, so the metric tasks get fed by live work.
6. **Record**: `coach.py task GAP ID done --note "<evidence>"`, or `start` if unfinished.

## Quiz grading

Pass = 2/3 correct without hints and the third corrected in their own words. Fail -> short re-teach with a different example, retry next session. Record only passes. If the host has a quiz widget, use it for the questions; otherwise ask in chat.

## Evidence standards for attest tasks

Accept: commit hashes or ranges, PR URLs, file paths plus what changed, pasted artifacts (the split plan, the debug log, the checklist). Reject or probe: "done", "I did it", evidence that does not match the task (e.g. a PR with 3k lines for a "<400 lines" task). Be kind but concrete about what is missing.

## Making modules feel like their code

Use the placeholders `coach.py module` fills ({god_file_1}, {largest_commit}, {risky_path_1}); when a placeholder falls back to generic text, ask the developer to pick the real file and use that.

## Staying honest

- Never mark a task done for the developer; never invent evidence.
- If a signal moves because of volume rather than habit (e.g. conventional % up because they stopped committing), say so.
- Celebrate concrete progress (a measurable delta), not effort.
