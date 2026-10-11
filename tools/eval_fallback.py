"""Score the local model + lint harness on request -> command cases.

    PYTHONPATH=src ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py [dev|frozen]

Each case: request, accept (regex the command must match; null = the right outcome is no command),
reference. `dev` is for tuning; `frozen` is for final comparison only — never tune on it.
Outcomes: pass, wrong (a command that fails `accept`), rejected (no command for an answerable
request: lint, model failure or abstention), abstain-ok / abstain-missed (for null-accept cases).
"""

import json
import re
import statistics
import sys
import time
from pathlib import Path

from whatisit_macos.local_recovery import suggest_local


def main() -> int:
    split = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    cases = [json.loads(line) for line in
             (Path(__file__).resolve().parents[1] / 'eval' / f'{split}.jsonl').read_text().splitlines()]
    counts = {'pass': 0, 'wrong': 0, 'rejected': 0, 'abstain-ok': 0, 'abstain-missed': 0}
    times = []
    for case in cases:
        start = time.perf_counter()
        answer = suggest_local(case['request'])
        times.append(time.perf_counter() - start)
        command = answer['command']
        if case['accept'] is None:
            label = 'abstain-missed' if command else 'abstain-ok'
        elif command is None:
            label = 'rejected'
        else:
            label = 'pass' if re.search(case['accept'], command) else 'wrong'
        counts[label] += 1
        if label not in ('pass', 'abstain-ok'):
            print(f"{label:15} {case['id']} {case['request']}\n{'':16}{command or answer['reason']}"
                  f"\n{'':16}ref: {case['reference']}")
    total = len(cases)
    print(f'\n{split}: ' + '  '.join(f'{k} {v}' for k, v in counts.items()) +
          f'  | correct {counts["pass"] + counts["abstain-ok"]}/{total}  p50 {statistics.median(times):.2f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
