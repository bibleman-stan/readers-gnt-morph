#!/usr/bin/env python3
"""
Inject generated chapter JSON into the HTML template to produce a standalone file.
"""
import glob
import json
import os
import sys

# Chapter counts per book are derived from the canonical registry in
# src/books.py — no need to duplicate here. Keyed by display name
# ("Acts", "Romans", "1 Corinthians") since that's what lives in the
# chapter JSON's `book` field.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import BOOKS, display_to_code

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chapters_for_display(display):
    code = display_to_code(display)
    return BOOKS[code]['chapters'] if code else 0


_BOOKS_PAYLOAD_CACHE = None
_VERSE_COUNTS_CACHE = None


def _books_payload():
    """Small object shipped to the template for the location picker.
    BOOK_KEYS is the canonical NT order (Matthew → Revelation)."""
    global _BOOKS_PAYLOAD_CACHE
    if _BOOKS_PAYLOAD_CACHE is None:
        ordered = sorted(BOOKS.items(), key=lambda kv: kv[1]['order'])
        _BOOKS_PAYLOAD_CACHE = {
            'books': {code: {'name': meta['display'], 'chapters': meta['chapters']}
                      for code, meta in ordered},
            'keys': [code for code, _ in ordered],
        }
    return _BOOKS_PAYLOAD_CACHE


_VERSE_COUNTS_FILE = os.path.join(_REPO_ROOT, 'build', 'verse_counts.json')


def _verse_counts():
    """Max-verse-per-chapter map {code: {chapter: max_verse}} for the
    location picker. Persisted to build/verse_counts.json so subsequent
    build_html.py subprocess invocations (from bulk_generate / sync_senselines)
    read the cache in O(1) instead of re-scanning 260 JSONs. Safe to cache:
    max verse per chapter is a MorphGNT corpus property that sense-line
    syncs don't change. Delete the file if you ever vendor new MorphGNT data."""
    global _VERSE_COUNTS_CACHE
    if _VERSE_COUNTS_CACHE is not None:
        return _VERSE_COUNTS_CACHE

    if os.path.exists(_VERSE_COUNTS_FILE):
        try:
            with open(_VERSE_COUNTS_FILE, 'r', encoding='utf-8') as f:
                _VERSE_COUNTS_CACHE = json.load(f)
                return _VERSE_COUNTS_CACHE
        except (IOError, ValueError):
            pass  # fall through and recompute

    counts = {}
    build_root = os.path.join(_REPO_ROOT, 'build')
    for code in BOOKS:
        book_dir = os.path.join(build_root, code)
        if not os.path.isdir(book_dir):
            continue
        counts[code] = {}
        for path in glob.glob(os.path.join(book_dir, '*.json')):
            fname = os.path.basename(path)
            try:
                chapter = int(os.path.splitext(fname)[0])
            except ValueError:
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
            except (IOError, ValueError):
                continue
            entries = doc.get('data', doc) if isinstance(doc, dict) else doc
            max_v = 0
            for e in entries:
                v = e.get('v') if isinstance(e, dict) else None
                if isinstance(v, int) and v > max_v:
                    max_v = v
            if max_v:
                counts[code][chapter] = max_v

    try:
        os.makedirs(os.path.dirname(_VERSE_COUNTS_FILE), exist_ok=True)
        with open(_VERSE_COUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(counts, f, sort_keys=True)
    except IOError:
        pass

    _VERSE_COUNTS_CACHE = counts
    return counts


def main():
    data_file = sys.argv[1] if len(sys.argv) > 1 else 'build/acts/9.json'
    template = sys.argv[2] if len(sys.argv) > 2 else 'templates/reader.html'
    output = sys.argv[3] if len(sys.argv) > 3 else 'docs/acts/9.html'

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(template, 'r', encoding='utf-8') as f:
        html = f.read()

    book = data.get('book', 'Acts')
    chapter = data.get('chapter', '?')
    total_chapters = _chapters_for_display(book)
    book_code = display_to_code(book) or ''

    ch_json = json.dumps(data['data'], ensure_ascii=False)
    lex_json = json.dumps(data['lex'], ensure_ascii=False)

    books_payload = _books_payload()
    books_json = json.dumps(books_payload['books'], ensure_ascii=False)
    keys_json = json.dumps(books_payload['keys'])
    verse_counts_json = json.dumps(_verse_counts())

    html = html.replace('CHAPTER_DATA_PLACEHOLDER', ch_json)
    html = html.replace('LEX_DATA_PLACEHOLDER', lex_json)
    html = html.replace('BOOK_NAME_PLACEHOLDER', book)
    html = html.replace('BOOK_CODE_PLACEHOLDER', book_code)
    html = html.replace('CHAPTER_NUM_PLACEHOLDER', str(chapter))
    html = html.replace('TOTAL_CHAPTERS_PLACEHOLDER', str(total_chapters))
    html = html.replace('BOOKS_DATA_PLACEHOLDER', books_json)
    html = html.replace('BOOK_KEYS_PLACEHOLDER', keys_json)
    html = html.replace('VERSE_COUNTS_PLACEHOLDER', verse_counts_json)

    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Built {output}: {len(data['data'])} entries, {len(data['lex'])} lexicon entries")


if __name__ == '__main__':
    main()
