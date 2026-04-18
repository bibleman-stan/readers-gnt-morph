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
"""

BOOKS = {
    'matthew':        {'display': 'Matthew',         'file': '61-Mt-morphgnt.txt',  'chapters': 28, 'order': 40},
    'mark':           {'display': 'Mark',            'file': '62-Mk-morphgnt.txt',  'chapters': 16, 'order': 41},
    'luke':           {'display': 'Luke',            'file': '63-Lk-morphgnt.txt',  'chapters': 24, 'order': 42},
    'john':           {'display': 'John',            'file': '64-Jn-morphgnt.txt',  'chapters': 21, 'order': 43},
    'acts':           {'display': 'Acts',            'file': '65-Ac-morphgnt.txt',  'chapters': 28, 'order': 44},
    'romans':         {'display': 'Romans',          'file': '66-Ro-morphgnt.txt',  'chapters': 16, 'order': 45},
    '1corinthians':   {'display': '1 Corinthians',   'file': '67-1Co-morphgnt.txt', 'chapters': 16, 'order': 46},
    '2corinthians':   {'display': '2 Corinthians',   'file': '68-2Co-morphgnt.txt', 'chapters': 13, 'order': 47},
    'galatians':      {'display': 'Galatians',       'file': '69-Ga-morphgnt.txt',  'chapters': 6,  'order': 48},
    'ephesians':      {'display': 'Ephesians',       'file': '70-Eph-morphgnt.txt', 'chapters': 6,  'order': 49},
    'philippians':    {'display': 'Philippians',     'file': '71-Php-morphgnt.txt', 'chapters': 4,  'order': 50},
    'colossians':     {'display': 'Colossians',      'file': '72-Col-morphgnt.txt', 'chapters': 4,  'order': 51},
    '1thessalonians': {'display': '1 Thessalonians', 'file': '73-1Th-morphgnt.txt', 'chapters': 5,  'order': 52},
    '2thessalonians': {'display': '2 Thessalonians', 'file': '74-2Th-morphgnt.txt', 'chapters': 3,  'order': 53},
    '1timothy':       {'display': '1 Timothy',       'file': '75-1Ti-morphgnt.txt', 'chapters': 6,  'order': 54},
    '2timothy':       {'display': '2 Timothy',       'file': '76-2Ti-morphgnt.txt', 'chapters': 4,  'order': 55},
    'titus':          {'display': 'Titus',           'file': '77-Tit-morphgnt.txt', 'chapters': 3,  'order': 56},
    'philemon':       {'display': 'Philemon',        'file': '78-Phm-morphgnt.txt', 'chapters': 1,  'order': 57},
    'hebrews':        {'display': 'Hebrews',         'file': '79-Heb-morphgnt.txt', 'chapters': 13, 'order': 58},
    'james':          {'display': 'James',           'file': '80-Jas-morphgnt.txt', 'chapters': 5,  'order': 59},
    '1peter':         {'display': '1 Peter',         'file': '81-1Pe-morphgnt.txt', 'chapters': 5,  'order': 60},
    '2peter':         {'display': '2 Peter',         'file': '82-2Pe-morphgnt.txt', 'chapters': 3,  'order': 61},
    '1john':          {'display': '1 John',          'file': '83-1Jn-morphgnt.txt', 'chapters': 5,  'order': 62},
    '2john':          {'display': '2 John',          'file': '84-2Jn-morphgnt.txt', 'chapters': 1,  'order': 63},
    '3john':          {'display': '3 John',          'file': '85-3Jn-morphgnt.txt', 'chapters': 1,  'order': 64},
    'jude':           {'display': 'Jude',            'file': '86-Jud-morphgnt.txt', 'chapters': 1,  'order': 65},
    'revelation':     {'display': 'Revelation',      'file': '87-Re-morphgnt.txt',  'chapters': 22, 'order': 66},
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
