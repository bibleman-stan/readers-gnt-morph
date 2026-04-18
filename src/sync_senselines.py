#!/usr/bin/env python3
"""
sync_senselines.py — Detect and regenerate chapters whose sense-line
source (in the sibling readers-gnt repo) has changed since we last built.

The morph-reader consumes sense-line files from
  C:/Users/bibleman/repos/readers-gnt/data/text-files/v4-editorial/
  (overridable via SENSE_LINES_DIR env var)

When Stan edits those files to refine line-breaks, the morph-reader
needs to regenerate affected chapters. This script uses SHA-256 hashes
(not mtimes — Windows/git resets mtimes on clones, making mtime
unreliable) stored in a manifest at build/sense_hashes.json. Any
mismatch between the current file hash and the stored hash means the
chapter is stale.

Usage:
  PYTHONIOENCODING=utf-8 python src/sync_senselines.py
    → Report which chapters are stale. Does not modify anything.

  PYTHONIOENCODING=utf-8 python src/sync_senselines.py --regen
    → Regenerate + rebuild stale chapters. Updates the manifest on success.

  PYTHONIOENCODING=utf-8 python src/sync_senselines.py --regen --book romans
    → Only check/regen within one book.
"""
import argparse
import concurrent.futures
import hashlib
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
_SENSE_DIR = os.environ.get(
    'SENSE_LINES_DIR',
    'C:/Users/bibleman/repos/readers-gnt/data/text-files/v4-editorial',
)
_MANIFEST = os.path.join(_REPO_ROOT, 'build', 'sense_hashes.json')


def sense_line_path(book_code, chapter):
    """Path to the sense-line file for one chapter, or None if not found."""
    entry = BOOKS.get(book_code)
    if not entry:
        return None
    sc = entry['sense_code']

    # Sense-line dirs are NN-<sense_code>; find whichever NN pairs with sc
    for d in os.listdir(_SENSE_DIR):
        parts = d.split('-', 1)
        if len(parts) == 2 and parts[1] == sc:
            ch_str = f'{chapter:02d}'
            return os.path.join(_SENSE_DIR, d, f'{sc}-{ch_str}.txt')
    return None


def file_sha(path):
    """SHA-256 of a file's contents, or None if file missing."""
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def load_manifest():
    if os.path.exists(_MANIFEST):
        with open(_MANIFEST, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_manifest(manifest):
    os.makedirs(os.path.dirname(_MANIFEST), exist_ok=True)
    with open(_MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def check_staleness(target_books=None):
    """Return (stale_list, missing_list, manifest). Each entry is
    (book_code, chapter, current_sha)."""
    manifest = load_manifest()
    stale = []
    missing_source = []

    books_to_check = target_books or list(BOOKS.keys())
    for code in books_to_check:
        if code not in BOOKS:
            continue
        for ch in range(1, BOOKS[code]['chapters'] + 1):
            key = f'{code}/{ch}'
            src = sense_line_path(code, ch)
            current = file_sha(src)
            if current is None:
                missing_source.append((code, ch, src))
                continue
            prior = manifest.get(key)
            if prior != current:
                stale.append((code, ch, current))
    return stale, missing_source, manifest


def regenerate(stale, manifest):
    """Regenerate + rebuild the stale chapters, then update the manifest."""
    if not stale:
        return 0
    print(f'Loading stems / lexicon / frequencies (once)…', file=sys.stderr)
    t0 = time.time()
    stems = gc.load_stems()
    lex = gc.load_lexicon()
    freq = gc.load_nt_frequencies()
    print(f'  loaded in {time.time()-t0:.1f}s', file=sys.stderr)

    template = os.path.join(_REPO_ROOT, 'templates', 'reader.html')
    build_html_py = os.path.join(_HERE, 'build_html.py')

    def one(code, chapter, new_sha):
        out_json = os.path.join(_REPO_ROOT, 'build', code, f'{chapter}.json')
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        output = gc.build_chapter(code, chapter, stems, lex, freq)
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        out_html = os.path.join(_REPO_ROOT, 'docs', code, f'{chapter}.html')
        os.makedirs(os.path.dirname(out_html), exist_ok=True)
        subprocess.run([sys.executable, build_html_py, out_json, template, out_html],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return (code, chapter, new_sha)

    done = 0
    tg = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, c, ch, sha) for c, ch, sha in stale]
        for f in concurrent.futures.as_completed(futs):
            c, ch, sha = f.result()
            manifest[f'{c}/{ch}'] = sha
            done += 1

    print(f'Regenerated {done} chapter(s) in {time.time()-tg:.1f}s', file=sys.stderr)
    save_manifest(manifest)
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--regen', action='store_true',
                    help='Regenerate + rebuild stale chapters (default: report only)')
    ap.add_argument('--book', action='append', dest='books',
                    help='Restrict to one book code; repeatable')
    args = ap.parse_args()

    stale, missing, manifest = check_staleness(args.books)

    if not stale and not missing:
        print('All in sync. No chapters stale.')
        return 0

    if missing:
        print(f'\nSense-line source not found for {len(missing)} chapter(s):',
              file=sys.stderr)
        for code, ch, path in missing[:10]:
            print(f'  {code}/{ch}  (expected at: {path})', file=sys.stderr)
        if len(missing) > 10:
            print(f'  … and {len(missing)-10} more', file=sys.stderr)

    if stale:
        print(f'\n{len(stale)} chapter(s) stale (sense-line hash mismatch):')
        for code, ch, _ in stale[:30]:
            print(f'  {code}/{ch}')
        if len(stale) > 30:
            print(f'  … and {len(stale)-30} more')

        if args.regen:
            regenerate(stale, manifest)
            print('\nManifest updated. Run `git add -A && git commit` to land changes.')
        else:
            print('\nRun with --regen to rebuild these.')

    return 0 if not stale else (0 if args.regen else 1)


if __name__ == '__main__':
    sys.exit(main())
