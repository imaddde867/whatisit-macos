# Contributing

Install with `python -m pip install -e .`, then run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.

The tool is a model plus a harness; commands are never hardcoded. Improve it by changing how the model is prompted, how its output is verified against the host (`maclint.py`), or which model is used. Check any change with `tools/eval_fallback.py` and keep the cases it scores separate from anything you tune on.

Do not add tests that run privileged or destructive commands. Do not commit credentials, private paths, logs or model files.
