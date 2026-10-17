# Stage 2 additions review

The 36 new records form 12 three-record families. Each family pairs one request with no operand and no `path` (empty target) with two answerable `--path` variants. There are 12 abstentions and 24 answers. The `source_id` groups each family, so related examples can be kept in the same training split.

The examples exercise macOS `wc`, `head`, `grep`, `sort`, `shasum`, `file`, `readlink`, `find`, `du`, `stat`, `ls`, and `xattr`. Every command is read-only. Paths containing spaces are quoted; option-looking basenames use a `./` prefix. The targets assume the CLI passes `path` as `Explicit inputs: {"path": ...}` as implemented in `local_recovery_worker.py`. An unbound request such as “this file” has no actual operand and therefore receives an empty target under the worker's `MACOS_PREFIX` rule.

Validation on macOS (Darwin): all 12 local man pages resolved successfully. A scratch fixture verified the command forms, including `stat -f '%z'`, `ls -ldO`, `xattr -l`, and a nested `find -type f`. The following repeatable check runs all 24 answer targets only against a temporary directory; it also checks the schema, family counts, and empty abstention targets:

```sh
python3 - <<'PY'
import collections
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

rows = [json.loads(line) for line in Path('data/distill/stage2-additions.jsonl').read_text().splitlines()]
lines = ['zeta', 'TODO: one', 'alpha', 'beta', 'TODO: two', 'gamma', 'omega']
content = ''.join(line + '\n' for line in lines)
assert len(rows) == 36
assert len({row['id'] for row in rows}) == 36
assert sorted(collections.Counter(row['source_id'] for row in rows).values()) == [3] * 12
assert sum(row['kind'] == 'abstain' and row['path'] is None and row['target'] == '' for row in rows) == 12
with tempfile.TemporaryDirectory(prefix='s2add-') as temp:
    root = Path(temp)
    for row in rows:
        if row['kind'] != 'answer':
            continue
        path = root / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        if row['target'].startswith(('find ', 'du ')):
            (path / 'nested').mkdir(parents=True)
            (path / 'nested' / 'sample.txt').write_text('sample\n')
        elif row['target'].startswith('readlink '):
            path.symlink_to('target.txt')
        else:
            path.write_text(content)
            if row['target'].startswith('xattr '):
                subprocess.run(['xattr', '-w', 'com.example.stage2', 'value', str(path)], check=True)
    for row in rows:
        if row['kind'] == 'answer':
            env = dict(os.environ, LC_ALL='C')
            result = subprocess.run(shlex.split(row['target']), cwd=root, env=env,
                                    text=True, capture_output=True)
            assert result.returncode == 0, (row['id'], result.stderr)
            tool = shlex.split(row['target'])[0]
            output = result.stdout
            if tool == 'wc':
                assert int(output.split()[0]) == len(lines), row['id']
            elif tool == 'head':
                assert output == ''.join(line + '\n' for line in lines[:5]), row['id']
            elif tool == 'grep':
                assert output == '2:TODO: one\n5:TODO: two\n', row['id']
            elif tool == 'sort':
                assert output == ''.join(line + '\n' for line in sorted(lines)), row['id']
            elif tool == 'shasum':
                assert output.split()[0] == hashlib.sha256(content.encode()).hexdigest(), row['id']
            elif tool == 'file':
                assert output.rstrip().endswith(': ASCII text'), row['id']
            elif tool == 'readlink':
                assert output == 'target.txt\n', row['id']
            elif tool == 'find':
                assert output.splitlines() == [row['path'] + '/nested/sample.txt'], row['id']
            elif tool == 'du':
                size, operand = output.split()
                assert int(size) >= 1 and (root / operand).resolve() == (root / row['path']).resolve(), row['id']
            elif tool == 'stat':
                assert output == str(len(content.encode())) + '\n', row['id']
            elif tool == 'ls':
                assert ' - ' in output and f' {len(content.encode())} ' in output
                assert output.rstrip().endswith(row['path']), row['id']
            elif tool == 'xattr':
                assert 'com.example.stage2: value' in output, row['id']
            else:
                raise AssertionError((row['id'], tool))
print('36 records; 24 scratch commands passed')
PY
```

The held-out evaluation set was not read to write these examples. No training outcome is claimed here; the integration pass should still apply its normal overlap gate and drop any colliding family.
