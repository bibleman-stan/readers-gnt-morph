#!/usr/bin/env python3
"""
audit_coverage.py — Pre-generation verb-stem coverage auditor.

Before committing to generate a book, verify that enough unique verb
lemmas have stem data in data/greek-inflexion/STEM_DATA/morphgnt_lexicon.yaml.
If coverage drops below a threshold (default 90%), fails out with a list
of missing lemmas ranked by frequency — so the user can either supplement
manually or accept the gaps explicitly.

Empirical note (2026-04-17): greek-inflexion already has ≥99% coverage
for every NT book except James (98.9%, one rare particle) and Galatians
(99.0%, one rare Aramaic compound). So this gate will nearly always pass,
but it's cheap insurance against future lexicon updates or new corpora.

Usage:
  PYTHONIOENCODING=utf-8 python src/audit_coverage.py romans
  PYTHONIOENCODING=utf-8 python src/audit_coverage.py --threshold 85 hebrews
  PYTHONIOENCODING=utf-8 python src/audit_coverage.py --all   # audits every book
"""
import argparse
import os
import sys
from collections import Counter

import yaml

# Local import — src/books.py sits next to this file
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from books import BOOKS

_REPO_ROOT = os.path.dirname(_HERE)
_DEFAULT_MORPHGNT_DIR = os.path.join(_REPO_ROOT, 'data', 'morphgnt')
_DEFAULT_STEMS = os.path.join(
    _REPO_ROOT, 'data', 'greek-inflexion', 'STEM_DATA', 'morphgnt_lexicon.yaml'
)


def load_morphgnt_verbs(morphgnt_path):
    """Return {lemma: count} for every V- POS entry in the MorphGNT file."""
    counts = Counter()
    with open(morphgnt_path, 'r', encoding='utf-8') as f:
        for line in f:
            cols = line.strip().split()
            if len(cols) < 7:
                continue
            if cols[1].startswith('V'):
                counts[cols[6]] += 1
    return counts


def _has_stems(entry):
    return isinstance(entry, dict) and bool(entry.get('stems'))


def audit_book(code, stems_db, threshold):
    """Compute coverage for one book. Return (pct, total, covered, missing_dict)."""
    entry = BOOKS.get(code)
    if not entry:
        return None
    path = os.path.join(_DEFAULT_MORPHGNT_DIR, entry['file'])
    if not os.path.exists(path):
        return None
    verbs = load_morphgnt_verbs(path)
    covered = sum(1 for lemma in verbs if _has_stems(stems_db.get(lemma)))
    total = len(verbs)
    pct = 100.0 * covered / total if total else 100.0
    missing = {l: c for l, c in verbs.items() if not _has_stems(stems_db.get(l))}
    return pct, total, covered, missing


def _bar(pct, width=20):
    filled = int(pct / (100.0 / width))
    return '█' * filled + '░' * (width - filled)


def print_report(code, result, threshold):
    display = BOOKS[code]['display']
    pct, total, covered, missing = result
    status = '✓ PASS' if pct >= threshold else '✗ FAIL'
    print(f'\n  {display:22s}  {_bar(pct)}  {pct:5.1f}%  '
          f'({covered}/{total})  {status}')
    if pct < threshold and missing:
        print(f'    Missing lemmas (top 20 by frequency):')
        for lemma, cnt in sorted(missing.items(), key=lambda x: -x[1])[:20]:
            print(f'      {lemma:25s}  {cnt}x')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('book', nargs='?', help='Book code (e.g. romans, hebrews). Omit with --all.')
    parser.add_argument('--all', action='store_true', help='Audit every book in registry')
    parser.add_argument('--threshold', type=float, default=90.0,
                        help='Minimum coverage percent to pass (default 90)')
    parser.add_argument('--stems', default=_DEFAULT_STEMS,
                        help='Path to morphgnt_lexicon.yaml')
    args = parser.parse_args()

    if not args.book and not args.all:
        parser.error('Specify a book code or pass --all')

    print(f'Loading stems database…', file=sys.stderr)
    with open(args.stems, 'r', encoding='utf-8') as f:
        stems_db = yaml.safe_load(f) or {}

    targets = list(BOOKS.keys()) if args.all else [args.book.lower()]
    if args.book and args.book.lower() not in BOOKS:
        print(f'ERROR: unknown book code "{args.book}". Known: '
              f'{", ".join(sorted(BOOKS.keys()))}', file=sys.stderr)
        sys.exit(2)

    print(f'\n{"═"*70}\n  Verb Stem Coverage Audit (threshold {args.threshold:.1f}%)\n{"═"*70}')

    any_fail = False
    for code in sorted(targets, key=lambda c: BOOKS[c]['order']):
        result = audit_book(code, stems_db, args.threshold)
        if result is None:
            print(f'  {BOOKS[code]["display"]:22s}  (file missing)')
            any_fail = True
            continue
        print_report(code, result, args.threshold)
        if result[0] < args.threshold:
            any_fail = True

    print()
    sys.exit(1 if any_fail else 0)


if __name__ == '__main__':
    main()
