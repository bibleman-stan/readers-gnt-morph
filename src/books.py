#!/usr/bin/env python3
"""
books.py — Canonical registry of New Testament books.

Single source of truth for per-book metadata used across the pipeline:
- generate_chapter.py (which MorphGNT file to read, what book_code to pass)
- build_html.py (how many chapters per book for inter-chapter nav)
- docs/index.html (the book picker grid — manual sync for now)
- any future book-aware tooling

Chapter counts were computed from max(BBCC) across the reference
column of each MorphGNT file (verified 2026-04-17). File names match
the vendored corpus at data/morphgnt/.

Book `code` is the URL slug used throughout: lowercase, spaces
removed, numeric prefixes kept (1corinthians, not first-corinthians).
The `order` field is the canonical NT position (Matthew=40 through
Revelation=66) for sorting.
`sense_code` matches the sibling readers-gnt repo's directory naming
(at data/text-files/v4-editorial/NN-<sense_code>/) — used to locate
sense-line files for colometric layout.
"""

BOOKS = {
    'matthew':        {'display': 'Matthew',         'file': '61-Mt-morphgnt.txt',  'chapters': 28, 'order': 40, 'sense_code': 'matt'},
    'mark':           {'display': 'Mark',            'file': '62-Mk-morphgnt.txt',  'chapters': 16, 'order': 41, 'sense_code': 'mark'},
    'luke':           {'display': 'Luke',            'file': '63-Lk-morphgnt.txt',  'chapters': 24, 'order': 42, 'sense_code': 'luke'},
    'john':           {'display': 'John',            'file': '64-Jn-morphgnt.txt',  'chapters': 21, 'order': 43, 'sense_code': 'john'},
    'acts':           {'display': 'Acts',            'file': '65-Ac-morphgnt.txt',  'chapters': 28, 'order': 44, 'sense_code': 'acts'},
    'romans':         {'display': 'Romans',          'file': '66-Ro-morphgnt.txt',  'chapters': 16, 'order': 45, 'sense_code': 'rom'},
    '1corinthians':   {'display': '1 Corinthians',   'file': '67-1Co-morphgnt.txt', 'chapters': 16, 'order': 46, 'sense_code': '1cor'},
    '2corinthians':   {'display': '2 Corinthians',   'file': '68-2Co-morphgnt.txt', 'chapters': 13, 'order': 47, 'sense_code': '2cor'},
    'galatians':      {'display': 'Galatians',       'file': '69-Ga-morphgnt.txt',  'chapters': 6,  'order': 48, 'sense_code': 'gal'},
    'ephesians':      {'display': 'Ephesians',       'file': '70-Eph-morphgnt.txt', 'chapters': 6,  'order': 49, 'sense_code': 'eph'},
    'philippians':    {'display': 'Philippians',     'file': '71-Php-morphgnt.txt', 'chapters': 4,  'order': 50, 'sense_code': 'phil'},
    'colossians':     {'display': 'Colossians',      'file': '72-Col-morphgnt.txt', 'chapters': 4,  'order': 51, 'sense_code': 'col'},
    '1thessalonians': {'display': '1 Thessalonians', 'file': '73-1Th-morphgnt.txt', 'chapters': 5,  'order': 52, 'sense_code': '1thess'},
    '2thessalonians': {'display': '2 Thessalonians', 'file': '74-2Th-morphgnt.txt', 'chapters': 3,  'order': 53, 'sense_code': '2thess'},
    '1timothy':       {'display': '1 Timothy',       'file': '75-1Ti-morphgnt.txt', 'chapters': 6,  'order': 54, 'sense_code': '1tim'},
    '2timothy':       {'display': '2 Timothy',       'file': '76-2Ti-morphgnt.txt', 'chapters': 4,  'order': 55, 'sense_code': '2tim'},
    'titus':          {'display': 'Titus',           'file': '77-Tit-morphgnt.txt', 'chapters': 3,  'order': 56, 'sense_code': 'titus'},
    'philemon':       {'display': 'Philemon',        'file': '78-Phm-morphgnt.txt', 'chapters': 1,  'order': 57, 'sense_code': 'phlm'},
    'hebrews':        {'display': 'Hebrews',         'file': '79-Heb-morphgnt.txt', 'chapters': 13, 'order': 58, 'sense_code': 'heb'},
    'james':          {'display': 'James',           'file': '80-Jas-morphgnt.txt', 'chapters': 5,  'order': 59, 'sense_code': 'jas'},
    '1peter':         {'display': '1 Peter',         'file': '81-1Pe-morphgnt.txt', 'chapters': 5,  'order': 60, 'sense_code': '1pet'},
    '2peter':         {'display': '2 Peter',         'file': '82-2Pe-morphgnt.txt', 'chapters': 3,  'order': 61, 'sense_code': '2pet'},
    '1john':          {'display': '1 John',          'file': '83-1Jn-morphgnt.txt', 'chapters': 5,  'order': 62, 'sense_code': '1john'},
    '2john':          {'display': '2 John',          'file': '84-2Jn-morphgnt.txt', 'chapters': 1,  'order': 63, 'sense_code': '2john'},
    '3john':          {'display': '3 John',          'file': '85-3Jn-morphgnt.txt', 'chapters': 1,  'order': 64, 'sense_code': '3john'},
    'jude':           {'display': 'Jude',            'file': '86-Jud-morphgnt.txt', 'chapters': 1,  'order': 65, 'sense_code': 'jude'},
    'revelation':     {'display': 'Revelation',      'file': '87-Re-morphgnt.txt',  'chapters': 22, 'order': 66, 'sense_code': 'rev'},
}


def display_to_code(display_name):
    """Resolve a display name like 'Acts' or '1 Corinthians' to its code slug."""
    target = display_name.strip()
    for code, meta in BOOKS.items():
        if meta['display'] == target:
            return code
    return None


def file_for(code):
    """Return the MorphGNT filename for a book code, or None."""
    entry = BOOKS.get(code)
    return entry['file'] if entry else None


def chapters_for(code_or_display):
    """Return chapter count for a code or display name, or 0 if unknown."""
    if code_or_display in BOOKS:
        return BOOKS[code_or_display]['chapters']
    code = display_to_code(code_or_display)
    return BOOKS[code]['chapters'] if code else 0
