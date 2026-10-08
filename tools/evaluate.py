"""Measure authored task contracts and lexical retrieval; never execute suggestions."""

import argparse
import json
import platform
import shutil
from pathlib import Path
from typing import Callable

from whatisit_macos.engine import suggest
from whatisit_macos.retrieval import search


def load_cases(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    identifiers = set()
    for case in cases:
        required = ('id', 'split', 'request', 'expected_status', 'rubric', 'manual_validation')
        if not isinstance(case, dict) or any(not isinstance(case.get(key), str) for key in required):
            raise ValueError('Each case needs string identity, split, request, status and review fields.')
        if not case['id'] or case['id'] in identifiers:
            raise ValueError('Case IDs must be nonempty and unique.')
        identifiers.add(case['id'])
        if (case['split'] not in {'dev', 'heldout'} or
                case['expected_status'] not in {'suggestion', 'needs-input', 'unsupported', 'ambiguous'} or
                not case['rubric'] or case['manual_validation'] != 'pending'):
            raise ValueError('Invalid split/status or missing pending manual review rubric.')
        docs = case.get('expected_docs')
        if not isinstance(docs, list) or any(not isinstance(tool, str) or not tool for tool in docs):
            raise ValueError('expected_docs must be a list of tool names.')
        if 'path' in case and not isinstance(case['path'], str):
            raise ValueError('path must be a string.')
        if 'expected_recipe' in case and not isinstance(case['expected_recipe'], str):
            raise ValueError('expected_recipe must be a string.')
    if not cases:
        raise ValueError('Evaluation needs at least one case.')
    return cases


def evaluate(cases: list[dict], index: Path | None = None, *, system: str = 'Darwin',
             which: Callable[[str], str | None] = lambda tool: '/usr/bin/' + tool) -> dict:
    rows, splits = [], {}
    for case in cases:
        answer = suggest(case['request'], system=system, which=which, path=case.get('path'))
        matches = (answer['status'] == case['expected_status'] and
                   answer.get('recipe_id') == case.get('expected_recipe'))
        hits = search(index, case['request']) if index else []
        retrieved = {hit['tool'] for hit in hits}
        docs_hit = bool(retrieved.intersection(case['expected_docs'])) if case['expected_docs'] else None
        row = {'id': case['id'], 'split': case['split'], 'status': answer['status'],
               'recipe_id': answer.get('recipe_id'), 'command': answer['command'],
               'expected_status': case['expected_status'], 'contract_match': matches,
               'retrieved_tools': sorted(retrieved), 'docs_hit_at_3': docs_hit if index else None}
        rows.append(row)
        counts = splits.setdefault(case['split'], {'tasks': 0, 'contract_matches': 0, 'suggestions': 0,
                                                  'unsupported': 0, 'needs_input': 0, 'ambiguous': 0,
                                                  'docs_eligible': 0, 'docs_hits_at_3': 0})
        counts['tasks'] += 1
        counts['contract_matches'] += matches
        counts['suggestions'] += answer['status'] == 'suggestion'
        counts['unsupported'] += answer['status'] == 'unsupported'
        counts['needs_input'] += answer['status'] == 'needs-input'
        counts['ambiguous'] += answer['status'] == 'ambiguous'
        counts['docs_eligible'] += bool(case['expected_docs']) and index is not None
        counts['docs_hits_at_3'] += bool(docs_hit) and index is not None
    return {'system': system, 'splits': splits, 'cases': rows,
            'command_correctness': 'Unmeasured: manual execution and semantic review pending.',
            'retrieval_metric': 'Any expected tool in top 3 chunks; not passage relevance or flag validation.'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=Path('eval/macos.jsonl'))
    parser.add_argument('--docs-index', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(load_cases(args.cases), args.docs_index,
                              system=platform.system(), which=shutil.which), indent=2))


if __name__ == '__main__':
    main()
