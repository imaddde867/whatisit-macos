"""Score the local model + lint harness on request -> command cases.

    PYTHONPATH=src ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py [dev|frozen] [model|lint]

Each case: request, accept (regex or list of regexes, any may match; null = the right outcome is no command),
reference. `dev` is for tuning; `frozen` is for final comparison only — never tune on it.
Outcomes: pass, wrong (a command that fails `accept`), rejected (no command for an answerable
request: lint, model failure or abstention), abstain-ok / abstain-missed (for null-accept cases).
"""

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

from whatisit_macos import local_recovery_worker


def main() -> int:
    split = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    harness = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] in ('model', 'lint') else 'lint'
    cases = [json.loads(line) for line in
             (Path(__file__).resolve().parents[1] / 'eval' / f'{split}.jsonl').read_text().splitlines()]
    if os.environ.get('EVAL_SYSTEM_PROMPT_FILE'):  # experiment: replace upstream's system prompt in-process
        from whatisit import config
        config.SYSTEM_PROMPT = Path(os.environ['EVAL_SYSTEM_PROMPT_FILE']).read_text().strip()
    counts = {'pass': 0, 'wrong': 0, 'rejected': 0, 'abstain-ok': 0, 'abstain-missed': 0}
    times, outcomes, details = [], {}, {}
    for case in cases:
        start = time.perf_counter()
        answer = local_recovery_worker.suggest({'request': case['request'], 'path': None}, harness=harness)
        times.append(time.perf_counter() - start)
        command = answer['command']
        if case['accept'] is None:
            label = 'abstain-missed' if command else 'abstain-ok'
        elif command is None:
            label = 'rejected'
        else:
            patterns = [case['accept']] if isinstance(case['accept'], str) else case['accept']
            label = 'pass' if any(re.search(p, command) for p in patterns) else 'wrong'
        counts[label] += 1
        outcomes[case['id']] = label
        reason = answer['reason']
        kind = 'other'
        if command is None:
            if reason == 'Local generation returned no complete command.':
                kind = 'empty_output'
            elif reason.startswith('Generated command is not valid on macOS: '):
                kind = 'lint'
            elif reason.endswith('flagged as dangerous.'):
                kind = 'danger'
        details[case['id']] = {'label': label, 'command': command, 'reason': reason,
                               'no_command_kind': kind}
        if label not in ('pass', 'abstain-ok') and '-q' not in sys.argv:
            print(f"{label:15} {case['id']} {case['request']}\n{'':16}{command or answer['reason']}"
                  f"\n{'':16}ref: {case['reference']}")
    total = len(cases)
    print(f'\n{split}/{harness}: ' + '  '.join(f'{k} {v}' for k, v in counts.items()) +
          f'  | correct {counts["pass"] + counts["abstain-ok"]}/{total}  p50 {statistics.median(times):.2f}s')
    Path(f'/tmp/eval-{split}-{harness}.json').write_text(json.dumps(outcomes))  # for diffing variants
    Path(f'/tmp/eval-{split}-{harness}-detail.json').write_text(json.dumps(details))
    return 0


if __name__ == '__main__':
    sys.exit(main())
