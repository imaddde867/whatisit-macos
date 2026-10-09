"""Pilot A/B/C lookup comparison; never execute suggested commands."""

import argparse
import hashlib
import importlib.util
from importlib.metadata import version
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from whatisit_macos.engine import suggest
from whatisit_macos.local_model import LocalModel, suggest_with_model
from whatisit_macos.retrieval import search
from tools.benchmark import summarize
from tools.evaluate import load_cases


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def baseline():
    directory = ROOT / 'eval/baseline'
    spec = importlib.util.spec_from_file_location('frozen_baseline', directory / 'engine.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recipes = json.loads((directory / 'recipes.json').read_text())
    module.load_recipes = lambda: recipes
    return module.suggest


def tree_rss(pid: int, processes: list[tuple[int, int, int]]) -> int:
    descendants = {pid}
    while True:
        expanded = descendants | {child for child, parent, _ in processes if parent in descendants}
        if expanded == descendants:
            return sum(rss * 1024 for child, _, rss in processes if child in descendants)
        descendants = expanded


def rss_bytes() -> int:
    return int(subprocess.check_output(['/bin/ps', '-o', 'rss=', '-p', str(os.getpid())],
                                       text=True, timeout=5).strip()) * 1024


def worker(mode: str, cases: list[dict], index: Path, model_path: Path | None, passes: int) -> dict:
    router = baseline() if mode == 'A' else suggest
    model = LocalModel(model_path) if mode == 'C' else None
    rows, times = [], []
    before = rss_bytes()
    try:
        for iteration in range(passes):
            for case in cases:
                prompt = []
                def select(messages):
                    prompt.extend(messages)
                    return model.select(messages)
                start = time.perf_counter()
                kwargs = dict(system=platform.system(), which=shutil.which, path=case.get('path'))
                if model:
                    answer = suggest_with_model(case['request'], index=index, select=select, **kwargs)
                else:
                    answer = router(case['request'], **kwargs)
                    if mode == 'B':
                        answer['documentation'] = search(index, case['request'])
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
                rows.append({'id': case['id'], 'pass': iteration, 'elapsed_ms': elapsed,
                             'answer': answer, 'prompt': prompt,
                             'contract_match': answer['status'] == case['expected_status'] and
                             answer.get('recipe_id') == case.get('expected_recipe')})
        metal_peak = None
        if model and model.model is not None:
            import mlx.core as mx
            metal_peak = mx.get_peak_memory()
    finally:
        if model:
            model.close()
    after = rss_bytes()
    metal_idle = None
    if model and model.load_ms is not None:
        import mlx.core as mx
        metal_idle = {'active_bytes': mx.get_active_memory(), 'cache_bytes': mx.get_cache_memory()}
    return {'rows': rows, 'first_response_ms': times[0],
            'warm_ms': summarize(times[1:]) if len(times) > 1 else None,
            'contract_matches': sum(row['contract_match'] for row in rows),
            'model_load_ms': model.load_ms if model else None,
            'self_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'mlx_peak_allocated_bytes': metal_peak,
            'mlx_after_unload': metal_idle,
            'idle_before_bytes': before, 'idle_after_unload_bytes': after,
            'idle_delta_bytes': after - before, 'model_released': model.model is None if model else None}


def measure(mode: str, cases: list[dict], index: Path, model: Path | None, passes: int) -> dict:
    command = [sys.executable, '-m', 'tools.experiment', '--worker', mode,
               '--docs-index', str(index.resolve()), '--passes', str(passes)]
    if model:
        command += ['--model', str(model.resolve())]
    samples, errors = [], []
    stop = threading.Event()
    start = time.perf_counter()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    def sample():
        while not stop.is_set():
            try:
                listing = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,rss='],
                                                  text=True, timeout=5)
                samples.append(tree_rss(process.pid, [tuple(map(int, line.split()))
                                                      for line in listing.splitlines()]))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                errors.append(str(error))
            stop.wait(.05)
    sampler = threading.Thread(target=sample)
    sampler.start()
    try:
        stdout, stderr = process.communicate(json.dumps(cases), timeout=180)
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    finally:
        stop.set()
        sampler.join()
    elapsed = (time.perf_counter() - start) * 1000
    if process.returncode:
        raise RuntimeError(f'{mode} worker failed ({process.returncode}): {stderr[:2000]}')
    report = json.loads(stdout)
    report.update(wall_ms=elapsed, sampled_tree_peak_rss_bytes=max(samples, default=0),
                  peak_rss_lower_bound_bytes=max(report['self_peak_rss_bytes'], max(samples, default=0)),
                  rss_samples=len(samples), sampling_errors=errors, runtime_stderr=stderr)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docs-index', type=Path, required=True)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--cases', type=Path, default=ROOT / 'eval/app-checks.jsonl')
    parser.add_argument('--passes', type=int, default=2)
    parser.add_argument('--fresh-runs', type=int, default=3)
    parser.add_argument('--worker', choices=['A', 'B', 'C'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('Resource measurements require macOS (byte-valued ru_maxrss and ps).')
    if args.passes < 1 or args.fresh_runs < 1:
        parser.error('passes and fresh-runs must be positive')
    if args.worker:
        if args.worker == 'C' and not args.model:
            parser.error('C requires --model')
        print(json.dumps(worker(args.worker, json.load(sys.stdin), args.docs_index, args.model, args.passes)))
        return
    cases = load_cases(args.cases)
    # Hash before timing: provenance work is not model-load or response latency.
    artifacts = {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name: sha256(path)
                 for path in [args.cases.resolve(), args.docs_index.resolve(),
                              ROOT / 'eval/baseline/engine.py', ROOT / 'eval/baseline/recipes.json',
                              ROOT / 'src/whatisit_macos/recipes.json', ROOT / 'src/whatisit_macos/local_model.py',
                              ROOT / 'src/whatisit_macos/engine.py', ROOT / 'tools/experiment.py']}
    model_files = {p.name: sha256(p) for p in sorted(args.model.iterdir()) if p.is_file()} if args.model else None
    swap_before = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'vm.swapusage'], text=True).strip()
    variants = {}
    for mode in ('A', 'B', 'C') if args.model else ('A', 'B'):
        fresh = [measure(mode, cases[:1], args.docs_index, args.model, 1) for _ in range(args.fresh_runs)]
        variants[mode] = {'fresh_wall_ms': summarize([r['wall_ms'] for r in fresh]),
                          'fresh_peak_tree_rss_bytes': summarize([r['sampled_tree_peak_rss_bytes'] for r in fresh]),
                          'fresh_runs': fresh, 'warm': measure(mode, cases, args.docs_index, args.model, args.passes)}
    report = {'measured_at': datetime.now(timezone.utc).isoformat(), 'macos': platform.mac_ver()[0],
              'architecture': platform.machine(), 'python': platform.python_version(),
              'runtime': {name: version(name) for name in ('mlx-lm', 'mlx', 'transformers')} if args.model else None,
              'artifacts_sha256': artifacts, 'model_files_sha256': model_files, 'variants': variants,
              'swap_before': swap_before,
              'swap_after': subprocess.check_output(['/usr/sbin/sysctl', '-n', 'vm.swapusage'], text=True).strip(),
              'method': 'A frozen three-recipe router; B expanded router + retrieval; C same catalog/inputs + model. '
                        'Fresh worker wall includes Python/import/retrieval/load/answer/unload/exit. '
                        'Warm includes retrieval and rendering, excludes first response and model loading. '
                        'Fresh KV cache per request. Filesystem caches not flushed. '
                        'Process-tree RSS sampled every 50ms plus ps overhead; may miss short peaks. '
                        'ru_maxrss is separate exact self RSS high-water; MLX peak allocations are separate, '
                        'not added to RSS because unified-memory overlap is unknown. '
                        'Idle sampled immediately after explicit unload, before worker exit. '
                        'No server or suggested command started. Swap is system-wide; pressure not measured. '
                        'Contract matches are not semantic accuracy; all cases are development evidence.'}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
