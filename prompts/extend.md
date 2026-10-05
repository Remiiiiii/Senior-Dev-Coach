# Prompt: add a new gap, rule or chat parser

```
In the senior-dev-coach repo, add <WHAT: e.g. a gap "observability" / a rule "migration-without-rollback" / a parser for Gemini exports>.
Constraints:
- Gaps live in references/gap-library.json (detectors, rules, success_signals, tasks with kind metric|attest|quiz). Every metric task needs a `verify` block using a metric that scripts/gitmetrics.py, chatmetrics.py or coach.py actually computes; add the metric if missing.
- New live rules go in run_check() in scripts/coach.py with a weight (soft|hard|critical), a message, a fix, and an agent instruction; document them in references/accountability.md.
- Never store secrets or raw chat in outputs; keep redaction tests passing.
- Add or extend a case in tests/test_pipeline.py and make `python3 tests/test_pipeline.py` pass.
- Do not touch unrelated files. Show me a diff summary by risk (state file format, hooks behavior, metrics) before finishing.
```
