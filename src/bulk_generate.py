#!/usr/bin/env python3
"""
bulk_generate.py — In-process batch regeneration of chapter JSON.

The per-chapter CLI (`generate_chapter.py --book X N`) spawns a fresh
Python subprocess for each chapter, each of which re-parses the
greek-inflexion stems YAML (~1000 KB), the morphological-lexicon
(~1700 KB), and scans all 27 MorphGNT files for NT-wide frequencies.
At 260 chapters, that's >1,000 CPU-seconds of redundant loading alone.

This script loads everything ONCE in a single Python process, then
iterates all chapters in a thread pool. Expected: ~30-60s for the
whole GNT instead of the ~400s subprocess-per-chapter baseline.

Usage:
  PYTHONIOENCODING=utf-8 python src/bulk_generate.py                  # all 27 books
  PYTHONIOENCODING=utf-8 python src/bulk_generate.py acts             # one book
  PYTHONIOENCODING=utf-8 python src/bulk_generate.py acts romans      # multiple books
  PYTHONIOENCODING=utf-8 python src/bulk_generate.py --workers 16 acts
  PYTHONIOENCODING=utf-8 python src/bulk_generate.py --no-build       # skip HTML build
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from books import BOOKS
import generate_chapter as gc

_REPO_ROOT = os.path.dirname(_HERE)


def generate_one(book_code, chapter, stems_db, lexicon, freq, *, build_html=True):
    """Write one chapter's JSON (and optionally the reader HTML). Returns tuple."""
    out_json = os.path.join(_REPO_ROOT, 'build', book_code, f'{chapter}.json')
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    output = gc.build_chapter(book_code, chapter, stems_db, lexicon, freq)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if build_html:
        out_html = os.path.join(_REPO_ROOT, 'docs', book_code, f'{chapter}.html')
        os.makedirs(os.path.dirname(out_html), exist_ok=True)
        template = os.path.join(_REPO_ROOT, 'templates', 'reader.html')
        # build_html is small; spawning it is fine. Could also inline later.
        subprocess.run([sys.executable,
                        os.path.join(_HERE, 'build_html.py'),
                        out_json, template, out_html],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (book_code, chapter)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('books', nargs='*', help='Book codes to regen (omit for all 27)')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--no-build', action='store_true', help='Skip HTML build step')
    args = ap.parse_args()

    targets = args.books or list(BOOKS.keys())
    unknown = [b for b in targets if b not in BOOKS]
    if unknown:
        print(f'ERROR: unknown book code(s): {unknown}', file=sys.stderr)
        sys.exit(2)

    print(f'Loading stems / lexicon / frequencies (once)…', file=sys.stderr)
    t0 = time.time()
    stems_db = gc.load_stems()
    lexicon = gc.load_lexicon()
    freq = gc.load_nt_frequencies()
    print(f'  loaded in {time.time()-t0:.1f}s', file=sys.stderr)

    jobs = [(c, ch) for c in targets for ch in range(1, BOOKS[c]['chapters'] + 1)]
    print(f'Generating {len(jobs)} chapters across {len(targets)} books '
          f'({"+build" if not args.no_build else "no build"}, '
          f'{args.workers} workers)…', file=sys.stderr)
    tg = time.time()

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(generate_one, c, ch, stems_db, lexicon, freq,
                          build_html=not args.no_build): (c, ch)
                for c, ch in jobs}
        for f in concurrent.futures.as_completed(futs):
            try:
                f.result()
                done += 1
                if done % 40 == 0:
                    print(f'  {done}/{len(jobs)} ({time.time()-tg:.0f}s)', file=sys.stderr)
            except Exception as e:
                book, ch = futs[f]
                print(f'FAILED {book}/{ch}: {e}', file=sys.stderr)

    print(f'Done: {done}/{len(jobs)} chapters in {time.time()-tg:.1f}s '
          f'(total incl. load: {time.time()-t0:.1f}s)', file=sys.stderr)


if __name__ == '__main__':
    main()
