"""Run with the wheel's Python from outside the repository; no suggestions executed."""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path

import whatisit_macos
from whatisit_macos.engine import load_recipes
from whatisit_macos.retrieval import Manual, build_index, search


def main():
    repository = Path(__file__).resolve().parents[1]
    package = Path(whatisit_macos.__file__).resolve()
    assert not package.is_relative_to(repository), 'Source-tree import leaked into wheel check'
    assert not Path.cwd().is_relative_to(repository), 'Run outside repository'
    assert not os.environ.get('PYTHONPATH'), 'Unset PYTHONPATH'
    assert not distribution('whatisit-macos').requires, 'Unexpected runtime dependencies'
    assert len(load_recipes()) == 6
    cli = str(Path(sys.executable).with_name('whatisit-macos'))
    capture = str(Path(sys.executable).with_name('whatisit-macos-build-docs'))
    assert subprocess.run([cli, '--version'], capture_output=True, check=True).stdout.strip() == b'0.1.0'
    catalog = subprocess.run([cli, '--json', '--list'], capture_output=True, text=True, check=True)
    assert len(json.loads(catalog.stdout)) == 6
    subprocess.run([capture, '--help'], capture_output=True, check=True)
    with tempfile.TemporaryDirectory() as directory:
        index = Path(directory) / 'manuals.sqlite3'
        if platform.system() == 'Darwin':
            inventory = subprocess.run([capture, str(index)], capture_output=True, text=True, check=True)
            assert json.loads(inventory.stdout)['documents'] >= 3
        else:
            build_index(index, [Manual('pmset', 'test:pmset', '/usr/bin/pmset', 'test',
                                       '2026-10-08', 'sleep assertions snapshot')])
        assert search(index, 'sleep assertions')
        result = subprocess.run([cli, '--json', '--docs-index', str(index), 'show sleep assertions'],
                                capture_output=True, text=True)
        answer = json.loads(result.stdout)
        assert answer['documentation'] and not answer.get('documentation_error')
        if platform.system() == 'Darwin' and shutil.which('pmset'):
            assert result.returncode == 0 and answer['command'] == 'pmset -g assertions'
        else:
            assert result.returncode == 2 and answer['command'] is None
        missing = subprocess.run([cli, '--json', '--docs-index', str(index.with_name('missing.sqlite3')),
                                  'show sleep assertions'], capture_output=True, text=True)
        missing_answer = json.loads(missing.stdout)
        assert missing_answer['documentation_error'] and not index.with_name('missing.sqlite3').exists()
    print('Installed wheel: assets, metadata, entry points, fresh index, lookup and missing index OK')


if __name__ == '__main__':
    main()
