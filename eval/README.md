# Evaluation seed

`cases.jsonl` preserves the original seven task types and adds paraphrases, ambiguity, and mutation requests. It is an authored seed set, not a held-out benchmark. `expected_status` describes today's prototype behavior; `expected_recipe` is present only for a supported task.

The tests use a simulated Darwin platform and tool availability. They check output contracts, not whether the command works on a Mac. The four unsupported original tasks are planned coverage, not correct answers earned by abstaining.

Before adding an LLM, expand the set and report:

| Measure | Definition |
| --- | --- |
| Useful correct coverage | Fully correct, sufficiently complete suggestions / all tasks. |
| Answer accuracy | Fully correct suggestions / tasks answered. |
| Abstention rate | Unsupported or unresolved responses / all tasks. |
| Wrong-platform rate | Suggestions using unsupported platform tools/flags / all tasks. |
| Clarification quality | Required inputs requested rather than invented; unnecessary questions recorded separately. |
| Resource cost | Cold/warm wall time and peak/resident RSS, with OS, hardware, model hash, and settings. |

Manually review semantics; exact command strings alone are not a correctness oracle. Multiple equivalent commands can work, and a familiar executable can still carry wrong flags. Record operation effects, output usefulness, permissions, and version constraints. Never execute arbitrary generated commands in the scorer on the everyday workstation.
