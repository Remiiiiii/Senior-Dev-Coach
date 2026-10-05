# Scoring rubric

Scale: **3 = solid mid-level, 4 = senior, 5 = staff+**. 1-2 = below mid. Half points are fine.
Every score needs a confidence (low/med/high) and 2-3 pieces of evidence. No evidence, no score: mark the dimension "not assessed".

| Dimension | 2 (below mid) | 3 (solid mid) | 4 (senior) | 5 (staff+) | Best evidence |
|---|---|---|---|---|---|
| `code_quality` | Large untested files, duplication, unclear names | Readable features, a few hotspots | Hotspots shrink over time; boundaries respected | Sets conventions others adopt | largest files, churn hotspots, diffs |
| `system_design` | Features bolted on; no module boundaries | Reasonable layering inside a feature | Clear boundaries; designs for growth and failure | Shapes architecture across teams/products | module layout, coupling, big refactors |
| `testing` | Rare tests, tests lag features | Tests exist, uneven on risky paths | Risk tests land with the change; CI blocks | Test strategy and tooling others rely on | test colocation %, risky-without-test % |
| `debugging` | Trial and error; pastes errors | Finds causes with effort | Hypothesis-driven; regression test per fix | Prevents classes of bugs systemically | fix commits, fix-after-ship %, chat |
| `security` | Secrets/permissions handled ad hoc | Basic auth and validation | Policy as code, deny/scope tests, no secrets in history | Threat-models proactively | secret signals, authz tests, rules files |
| `git_process` | Huge vague commits | Mixed quality | Small conventional commits, reviewable PRs, green CI | Process others copy | files/commit, conventional %, PR sizes |
| `requirements` | Asks are vague | Clear for simple features | Constraints, non-goals, acceptance criteria up front | Aligns stakeholders and sequences work | chat sample, issue/PR text |
| `product_judgment` | Builds what is asked | Sensible prioritization | Sequences by value and risk; cuts scope | Drives strategy | roadmap/commit themes, chat |
| `ai_usage` | Accepts output blindly | Uses AI productively, reviews some | Owns every diff; constraints and tests in prompts | Builds guardrails and workflows for AI use | agent share, diff size, fix-after-ship, chat |
| `learning_velocity` | Repeats same mistakes | Learns when forced | Visible growth month over month | Raises the learning rate of others | commits/month trend, new subsystems |

## Calibration rules

- Output is not seniority. High commit volume with sprawling changes can still be a 2 on `git_process`.
- Strong product/security instinct can coexist with weak process. Score each dimension on its own evidence; do not average a verdict out of vibes.
- Overall placement: weight dimensions by the target role, state the weighting, and keep the verdict to one of: junior / mid / senior-leaning / senior / staff-track.
- With fewer than 10 owned commits or no chat data, cap confidence at `low` for dependent dimensions.
- Compare against the previous scorecard when one exists and report deltas, not just levels.

## Dimension -> gap ids (default mapping)

code_quality -> modular-architecture, change-hygiene | system_design -> modular-architecture | testing -> test-as-gate, operational-predictability |
debugging -> debugging-method | security -> security-hygiene | git_process -> change-hygiene, operational-predictability |
requirements -> requirements-clarity | ai_usage -> ai-ownership, requirements-clarity
