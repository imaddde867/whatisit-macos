"""Benchmark lookup only: fresh CLI processes and repeated in-process queries on macOS."""

import argparse
import hashlib
import json
import math
import platform
import re
import resource
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from whatisit_macos.engine import LogFilter, suggest
from whatisit_macos.retrieval import search
from tools.evaluate import load_cases


def summarize(values: list[float]) -> dict:
    if not values:
        raise ValueError('At least one sample is required.')
    ordered = sorted(values)
    return {'samples': len(values), 'median': statistics.median(values),
            'p95': ordered[math.ceil(len(values) * .95) - 1], 'max': ordered[-1]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docs-index', type=Path, required=True)
    parser.add_argument('--cases', type=Path, default=Path('eval/macos.jsonl'))
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('This measurement uses macOS time -l and byte-valued ru_maxrss.')
    cases = load_cases(args.cases)
    warm = {name: [] for name in ('baseline', 'retrieval', 'combined')}
    for _ in range(5):
        for case in cases:
            for name in warm:
                start = time.perf_counter()
                if name != 'retrieval':
                    suggest(case['request'], system='Darwin', which=shutil.which, path=case.get('path'),
                            log_filter=LogFilter(**case['log_filter']) if 'log_filter' in case else None)
                if name != 'baseline':
                    search(args.docs_index, case['request'])
                warm[name].append((time.perf_counter() - start) * 1000)
    warm_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2
    cold = {}
    for name in ('baseline', 'with_documentation'):
        elapsed, rss = [], []
        for _ in range(10):
            command = ['/usr/bin/time', '-l', sys.executable, '-m', 'whatisit_macos', '--json']
            if name == 'with_documentation':
                command += ['--docs-index', str(args.docs_index.resolve())]
            command += ['show sleep assertions']
            start = time.perf_counter()
            process = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
            elapsed.append((time.perf_counter() - start) * 1000)
            answer = json.loads(process.stdout)
            assert answer['command'] == 'pmset -g assertions', 'Benchmark lookup changed'
            if name == 'with_documentation':
                assert answer['documentation'] and not answer.get('documentation_error')
            match = re.search(r'(\d+)\s+maximum resident set size', process.stderr)
            if not match:
                raise RuntimeError('macOS time did not report peak RSS.')
            rss.append(int(match.group(1)) / 1024**2)
        cold[name] = {'wall_ms': summarize(elapsed), 'peak_rss_mib': summarize(rss)}
    report = {'measured_at': datetime.now(timezone.utc).isoformat(), 'macos_version': platform.mac_ver()[0],
              'architecture': platform.machine(), 'python': platform.python_version(),
              'sqlite': sqlite3.sqlite_version, 'index_bytes': args.docs_index.stat().st_size,
              'index_sha256': hashlib.sha256(args.docs_index.read_bytes()).hexdigest(),
              'cases_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
              'warm_ms': {name: summarize(values) for name, values in warm.items()},
              'warm_process_peak_rss_mib': warm_peak, 'fresh_process': cold,
              'method': 'Warm: 5 passes over 40 tasks, includes index open/query/close. '
                        'Fresh: 10 processes per mode, one sleep query, includes Python/CLI startup '
                        'and time wrapper; OS filesystem caches are not flushed. RSS from time -l '
                        'is bytes on macOS. No suggested command is executed.'}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
