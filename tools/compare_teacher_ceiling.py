"""Join the teacher-ceiling report with student and baseline per-case labels.

    python3 tools/compare_teacher_ceiling.py <teacher-report.json>

Prints the teacher-majority x student 2x2 (f16 seed 42, untrained zero-update
f16, stage-2 Q4 and default arms), the teacher-right/student-wrong cases with
the teacher command and the reference, and per-split teacher counts.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_labels(stem):
    labels = {}
    for split in ('dev', 'everyday'):
        labels.update(json.loads(
            (ROOT / 'data/teacher/eval-ceiling/f16-labels' / f'{stem}-{split}.json').read_text()))
    return labels


def main() -> int:
    report = json.loads(Path(sys.argv[1]).read_text())
    arms = json.loads((ROOT / 'docs/stage2-arm-labels.json').read_text())['arms']
    students = {
        'f16 seed42': load_labels('s42f16'),
        'zero f16': load_labels('zerof16'),
        'stage2 Q4': {**arms['stage2-lr1e-5-s42']['dev'],
                      **arms['stage2-lr1e-5-s42']['everyday']},
        'default': {**arms['default']['dev'], **arms['default']['everyday']},
    }

    def correct(label):
        return label in ('pass', 'abstain-ok')

    teacher = {case_id: result['majority']
               for case_id, result in report['per_case'].items()}
    cases = {}
    for split in ('dev', 'everyday'):
        for line in (ROOT / 'eval' / f'{split}.jsonl').read_text().splitlines():
            if line.strip():
                case = json.loads(line)
                cases[case['id']] = (split, case)

    for name, labels in students.items():
        matrix = Counter()
        for case_id, teacher_label in teacher.items():
            matrix[(correct(teacher_label), correct(labels[case_id]))] += 1
        print(f"2x2 teacher-majority x {name}: "
              f"TT {matrix[(True, True)]}  TS {matrix[(True, False)]}  "
              f"ST {matrix[(False, True)]}  SS {matrix[(False, False)]}")

    student = students['f16 seed42']
    print('\nteacher-right / f16-student-wrong:')
    rows = [case_id for case_id in sorted(teacher)
            if correct(teacher[case_id]) and not correct(student[case_id])]
    for case_id in rows:
        split, case = cases[case_id]
        result = report['per_case'][case_id]
        print(f"{case_id} [{split}] teacher={result['majority']} "
              f"student={student[case_id]}")
        print(f"    request: {case['request']}")
        print(f"    reference: {case['reference']}")
        print(f"    teacher: {result['majority_command']}")
    print('count:', len(rows))

    for split in ('dev', 'everyday'):
        total = sum(1 for case_id, (s, _) in cases.items() if s == split)
        right = sum(1 for case_id in teacher
                    if cases[case_id][0] == split and correct(teacher[case_id]))
        print(f"teacher majority correct {split}: {right}/{total}")
    print(f"teacher majority correct pooled: "
          f"{sum(correct(t) for t in teacher.values())}/{len(teacher)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
