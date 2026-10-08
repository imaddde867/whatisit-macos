# Contributing

Install in a virtual environment with `python -m pip install -e .`, then run `python -m unittest discover -s tests -v`.

For a new recipe:

1. Check the command and flags in the current macOS manual or official documentation.
2. Add a fixed argument template, explicit parameters, references, and meaningful caveats to `src/whatisit_macos/recipes.json`.
3. Add positive paraphrases and negative/ambiguous cases. A lexical match must not be presented as proof of full task correctness.
4. Record macOS/device validation separately from unit tests. Do not add tests that run privileged or destructive commands on a contributor's machine.

The starter renderer currently supports only a `path` parameter. Extend it explicitly for other typed inputs instead of accepting arbitrary shell fragments. Keep dependencies and background services out unless measurements justify them.

Do not commit credentials, private file paths, logs, model files, or copied manual-page corpora. The evaluation fixtures use generic questions and paths.
