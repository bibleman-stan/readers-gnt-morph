#!/usr/bin/env python3
"""
validate_glosses.py — Quality gate for inflected English glosses.

Two layers of checking:
  1. Anti-pattern scan: catches obviously broken output ("was am",
     "had X-s", "will VERB-ed") in the rendered chapter HTML.
  2. Ground-truth test set: a curated list of (Greek form, expected
     gloss) pairs. Verifies the inflection engine emits the right
     English for known cases across the tense/voice grid.

Run after rebuilding chapters and before committing any
inflection-engine changes.

Usage:
  PYTHONIOENCODING=utf-8 python src/validate_glosses.py docs/acts/9.html
  PYTHONIOENCODING=utf-8 python src/validate_glosses.py --testset
"""
import json
import re
import sys
from pathlib import Path


# ═══════════════════════════════════════════
# ANTI-PATTERN SCANNER
# ═══════════════════════════════════════════
# Patterns that should NEVER appear in a rendered gloss. Each entry:
#   (regex, label, why-it-is-bad)
ANTI_PATTERNS = [
    (r'\bwas am\b',        'AUX_DOUBLE',     'auxiliary stack: "was am X" (broken aux strip)'),
    (r'\bwas is\b',        'AUX_DOUBLE',     'auxiliary stack: "was is X"'),
    (r'\bwas are\b',       'AUX_DOUBLE',     'auxiliary stack: "was are X"'),
    (r'\bwas be\b',        'AUX_DOUBLE',     'auxiliary stack: "was be X"'),
    (r'\bhad am\b',        'AUX_DOUBLE',     'auxiliary stack: "had am X"'),
    (r'\bhad been been\b', 'AUX_DOUBLE',     'auxiliary stack: "had been been X"'),
    (r'\bwill is\b',       'AUX_DOUBLE',     'auxiliary stack: "will is X"'),
    (r'\bwill be be\b',    'AUX_DOUBLE',     'auxiliary stack: "will be be X"'),
    (r'\bbeing being\b',   'AUX_DOUBLE',     'gerund-of-aux: "being being X"'),
    (r'\bing\b',           'BARE_ING',       'orphan "ing" — likely toGerund on empty'),
    (r'\bwithing\b',       'PHRASAL_BREAK',  '"-ing" appended to preposition (phrasal verb mishandled)'),
    (r'\buponing\b',       'PHRASAL_BREAK',  '"-ing" appended to "upon"'),
    (r'\baparting\b',      'PHRASAL_BREAK',  '"-ing" appended to "apart"'),
    (r'\baboutening\b',    'PHRASAL_BREAK',  '"-ing" appended to "about"'),
    (r'\btoing\b',         'PHRASAL_BREAK',  '"-ing" appended to "to"'),
    (r'\bouting\b',        'PHRASAL_BREAK',  '"-ing" appended to "out"'),
    (r'\boffing\b',        'PHRASAL_BREAK',  '"-ing" appended to "off"'),
]


def _collect_glosses_from_json(json_path):
    """Pull every (greek, lemma, tvm, gloss) tuple from a chapter JSON.
    Glosses include both 'igl' (build-time inflected) and the bare
    lex-table entries when no igl is present.
    """
    data = json.loads(Path(json_path).read_text(encoding='utf-8'))
    pairs = []
    lex = data.get('lex', {})
    for d in data.get('data', []):
        if not isinstance(d, dict) or 'lem' not in d:
            continue
        lemma = d.get('lem', '')
        gloss = d.get('igl') or lex.get(lemma, {}).get('gl', '')
        if gloss:
            pairs.append({
                'greek': d.get('txt', ''),
                'lemma': lemma,
                'tvm': d.get('tvm', ''),
                'gloss': gloss,
                'source': 'igl' if 'igl' in d else 'bare',
            })
    return pairs


def scan_chapter(path):
    """Scan a chapter for anti-pattern glosses. Accepts JSON or HTML.

    HTML path is reinterpreted as the matching build/<book>/<N>.json
    so we can inspect the precomputed igl values rather than chasing
    DOM that's only realized client-side.
    """
    p = Path(path)
    if p.suffix == '.html':
        # docs/acts/9.html -> build/acts/9.json
        rel = p.relative_to(p.parents[2]) if len(p.parents) >= 3 else p
        # parents[2] is the repo root; rel = 'docs/acts/9.html'
        # We just want the chapter slug at p.parent.name + p.stem
        json_candidate = p.parents[2] / 'build' / p.parent.name / (p.stem + '.json')
        if json_candidate.exists():
            p = json_candidate

    glosses = _collect_glosses_from_json(p)

    findings = []
    for g in glosses:
        for pat, label, why in ANTI_PATTERNS:
            if re.search(pat, g['gloss'], re.IGNORECASE):
                findings.append({**g, 'label': label, 'why': why})
                break

    return {
        'path': str(p),
        'total_glosses': len(glosses),
        'inflected': sum(1 for g in glosses if g['source'] == 'igl'),
        'findings': findings,
    }


def print_chapter_report(report, label):
    print(f'\n{"="*60}')
    print(f'  Gloss anti-pattern scan: {label}')
    print(f'{"="*60}')
    print(f'  Total glossed words: {report["total_glosses"]}')
    print(f'  Build-time inflected: {report["inflected"]}')
    print(f'  Anti-pattern hits: {len(report["findings"])}')
    if report['findings']:
        print('\nFINDINGS:')
        by_label = {}
        for f in report['findings']:
            by_label.setdefault(f['label'], []).append(f)
        for lab, items in sorted(by_label.items()):
            print(f'\n  [{lab}] {items[0]["why"]}')
            for it in items[:10]:
                print(f'    {it["greek"]:18s} {it["lemma"]:14s} {it["tvm"]:3s}  "{it["gloss"]}"')
            if len(items) > 10:
                print(f'    ... and {len(items)-10} more')
    else:
        print('  ✓ No anti-pattern hits.')


# ═══════════════════════════════════════════
# GROUND-TRUTH TEST SET
# ═══════════════════════════════════════════
# Each entry: (Greek surface form, lemma, parsing, expected English gloss).
# Parsing format matches MorphGNT: 8-char string of
#   person, tense, voice, mood, case, number, gender, degree.
# Sourced from Acts; all are forms that actually appear in the corpus.
TEST_SET = [
    # Aorist active indicative → simple past
    # ποιέω Dodson "I do, make" — first sense "do" → did
    ('ἐποίησα',    'ποιέω',     '1AAI-S--', 'did'),
    ('ἐποίησεν',   'ποιέω',     '3AAI-S--', 'did'),
    ('εἶπεν',      'λέγω',      '3AAI-S--', 'said'),
    ('ἤκουσαν',    'ἀκούω',     '3AAI-P--', 'heard'),
    ('ἔγραψεν',    'γράφω',     '3AAI-S--', 'wrote'),
    # Aorist middle indicative → simple past (middle treated as active)
    ('ἐξελέξατο',  'ἐκλέγομαι', '3AMI-S--', 'chose'),
    ('ἐγένετο',    'γίνομαι',   '3AMI-S--', 'became'),
    # Aorist passive indicative → "was X-ed"
    ('ἀνελήμφθη',  'ἀναλαμβάνω', '3API-S--', 'was taken up'),
    ('ἐπληρώθη',   'πληρόω',    '3API-S--', 'was fulfilled'),
    # Aorist passive of deponents (lemma -μαι, active gloss) → simple past
    ('ἀπεκρίθη',   'ἀποκρίνομαι', '3API-S--', 'answered'),
    ('ἐπορεύθη',   'πορεύομαι',  '3API-S--', 'went'),
    ('ἐδυνήθη',    'δύναμαι',    '3API-S--', 'was able'),
    # Imperfect → "was X-ing"
    ('ἤκουεν',     'ἀκούω',     '3IAI-S--', 'was hearing'),
    ('ἐδίδασκεν',  'διδάσκω',   '3IAI-S--', 'was teaching'),
    # Present indicative → bare
    ('λέγει',      'λέγω',      '3PAI-S--', 'say'),
    ('ἀκούετε',    'ἀκούω',     '2PAI-P--', 'hear'),
    # Present passive → "is X-ed"
    ('λέγεται',    'λέγω',      '3PPI-S--', 'is said'),
    # Future → "will X"
    ('ἀκούσεται',  'ἀκούω',     '3FMI-S--', 'will hear'),
    ('λήμψεσθε',   'λαμβάνω',   '2FMI-P--', 'will take'),
    # Future passive → "will be X-ed"
    ('ἀκουσθήσεται', 'ἀκούω',  '3FPI-S--', 'will be heard'),
    # Perfect active → "have X-ed"
    ('γέγραπται',  'γράφω',     '3XPI-S--', 'has been written'),
    ('ἀκήκοα',     'ἀκούω',     '1XAI-S--', 'have heard'),
    # Stative override: εἰμί
    ('ἦν',         'εἰμί',      '3IAI-S--', 'was'),
    ('ἐστιν',      'εἰμί',      '3PAI-S--', 'is'),
    ('ἔσται',      'εἰμί',      '3FMI-S--', 'will be'),
    # Stative override: οἶδα (perfect form, present meaning)
    ('οἶδα',       'οἶδα',      '1XAI-S--', 'know'),
    ('οἴδατε',     'οἶδα',      '2XAI-P--', 'know'),
    # μέλλω override (already a phrase)
    ('ἔμελλεν',    'μέλλω',     '3IAI-S--', 'was about to'),
    # δεῖ override (impersonal)
    ('δέω',        'δέω',       '3PAI-S--', 'it is necessary'),
    ('ἔδει',       'δέω',       '3IAI-S--', 'it was necessary'),
    # Phrasal verb head-only inflection
    ('ἀφώρισεν',   'ἀφορίζω',   '3AAI-S--', 'set apart'),  # set is its own past
]


# ═══════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════

# A small lexicon used only by the test runner. Maps lemma -> bare gloss
# the way generate_chapter.py would resolve it from morphological-lexicon.
# Sourced manually for the verbs in TEST_SET.
TEST_LEXICON = {
    'ποιέω':       'do',         # MorphGNT often "I make, do"
    'λέγω':        'say',
    'ἀκούω':       'hear',
    'γράφω':       'write',
    'ἐκλέγομαι':   'choose',
    'γίνομαι':     'become',
    'ἀναλαμβάνω':  'take up',
    'πληρόω':      'fulfill',
    'ἀποκρίνομαι': 'answer',
    'πορεύομαι':   'go',
    'δύναμαι':     'I am able',  # stative gloss as Dodson gives it
    'διδάσκω':     'teach',
    'λαμβάνω':     'take',
    'εἰμί':        'I am',
    'οἶδα':        'know',
    'μέλλω':       'I am about to',
    'δέω':         'it is necessary',
    'ἀφορίζω':     'set apart',
}


def run_testset():
    """Run the inflection engine against TEST_SET and report mismatches."""
    from inflect_gloss import inflect_gloss

    passed, failed = 0, []
    for greek, lemma, parsing, expected in TEST_SET:
        bare = TEST_LEXICON.get(lemma, '')
        if not bare:
            failed.append((greek, lemma, parsing, expected, '(no bare gloss in TEST_LEXICON)'))
            continue
        # Override matches use 'I X' stripped; do that here so test
        # mirrors what generate_chapter.py does.
        for lead in ('I ', 'a ', 'an ', 'the '):
            if bare.startswith(lead):
                bare = bare[len(lead):]
                break
        tvm = parsing[1:4]
        actual = inflect_gloss(bare, tvm, lemma)
        if actual == expected:
            passed += 1
        else:
            failed.append((greek, lemma, parsing, expected, actual))

    print(f'\n{"="*60}')
    print(f'  Ground-truth test set')
    print(f'{"="*60}')
    print(f'  Passed: {passed}/{len(TEST_SET)}')
    if failed:
        print(f'  Failed: {len(failed)}')
        for greek, lemma, parsing, expected, actual in failed:
            print(f'    {greek:14s} {lemma:14s} {parsing}')
            print(f'      expected: "{expected}"')
            print(f'      actual:   "{actual}"')
    else:
        print('  ✓ all forms match.')
    return len(failed) == 0


def main():
    args = sys.argv[1:]
    if not args or args[0] == '--testset':
        ok = run_testset()
        sys.exit(0 if ok else 1)

    # Otherwise treat each arg as an HTML or JSON chapter file
    all_clean = True
    for path in args:
        report = scan_chapter(path)
        print_chapter_report(report, path)
        if report['findings']:
            all_clean = False
    sys.exit(0 if all_clean else 1)


if __name__ == '__main__':
    main()

