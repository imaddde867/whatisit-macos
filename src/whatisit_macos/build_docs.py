"""Explicitly capture system manuals and recipe text; never run catalog commands."""

import argparse
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from whatisit_macos.engine import load_recipes
from whatisit_macos.retrieval import Manual, build_index

SYSTEM_PATH = '/usr/bin:/usr/sbin:/bin:/sbin'

TOOLS = (('system_profiler', '8'), ('pmset', '1'), ('mdls', '1'), ('fs_usage', '1'),
         ('launchctl', '1'), ('log', '1'), ('codesign', '1'), ('spctl', '8'),
         ('stat', '1'), ('find', '1'), ('sed', '1'), ('du', '1'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('Capture requires macOS; lookup/tests are portable.')
    if args.index.exists():
        parser.error('Index already exists. Choose a new capture filename.')
    version = subprocess.run(['/usr/bin/sw_vers', '-productVersion'], capture_output=True,
                             text=True, check=True, timeout=10).stdout.strip()
    captured = datetime.now(timezone.utc).isoformat()
    environment = {**os.environ, 'MANPAGER': '/bin/cat', 'PAGER': '/bin/cat', 'MANWIDTH': '100'}
    environment.pop('MANOPT', None)
    manuals, inventory = [], []
    for tool, section in TOOLS:
        binary = shutil.which(tool, path=SYSTEM_PATH)
        location = subprocess.run(['/usr/bin/man', '-M', '/usr/share/man', '-w', section, tool],
                                  capture_output=True, text=True, timeout=10, env=environment)
        source = location.stdout.strip()
        if not binary or location.returncode or not source:
            inventory.append({'tool': tool, 'tool_path': binary, 'status': 'unavailable'})
            continue
        rendered = subprocess.run(['/usr/bin/man', '-M', '/usr/share/man', section, tool],
                                  capture_output=True, text=True, check=True, timeout=10, env=environment)
        text = subprocess.run(['/usr/bin/col', '-b'], input=rendered.stdout, capture_output=True,
                              text=True, check=True, timeout=10).stdout
        manuals.append(Manual(tool, source, binary, version, captured, text))
        inventory.append({'tool': tool, 'tool_path': binary, 'source': source, 'status': 'captured'})
    for recipe in load_recipes():
        tool = recipe['argv'][0]
        binary = shutil.which(tool, path=SYSTEM_PATH)
        if binary:
            text = '\n'.join([recipe['title'], ' '.join(recipe['argv']),
                              ' '.join(word for group in recipe['match_groups'] for word in group),
                              *recipe['notes'], *recipe['sources']])
            manuals.append(Manual(tool, 'catalog:' + recipe['id'], binary, version, captured, text))
    assert manuals and all(manual.text.strip() for manual in manuals), 'No usable documents captured'
    build_index(args.index, manuals)
    print(json.dumps({'macos_version': version, 'captured_at': captured, 'inventory': inventory,
                      'documents': len(manuals), 'index_bytes': args.index.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
