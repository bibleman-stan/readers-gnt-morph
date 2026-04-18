#!/usr/bin/env python3
"""
validate_chapter.py — Automated validator for generated chapter JSON.

Runs a battery of rule-based checks against the decomposed morphology.
Greek has a finite grammar, so every expected pattern can be verified.
Flags findings by category so the user can review in bulk instead of
eyeballing every word.

Usage: python validate_chapter.py acts13_data.json
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict, Counter


# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def strip_punct(s):
    """Remove punctuation/editorial marks for surface comparison.
    Matches morpheus.clean_surface() + normalizes apostrophe variants."""
    s = re.sub(r'[⸀⸁⸂⸃⸄⸅⁰¹²³⁴⁵⁶⁷⁸⁹]', '', s or '')
    # Normalize apostrophe variants: U+02BC, U+2019, U+0027 → single form
    s = s.replace('\u02bc', "'").replace('\u2019', "'")
    return s.strip('.,;·:?!')


def na(s):
    """Strip accents and normalize apostrophes for comparison."""
    s = (s or '').replace('\u02bc', "'").replace('\u2019', "'")
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn').lower()


# Load the stems database lazily for compound detection
_STEMS_DB = None
def get_stems_db():
    global _STEMS_DB
    if _STEMS_DB is None:
        try:
            import yaml, os
            path = os.path.join(os.path.dirname(__file__), '..',
                                'data', 'greek-inflexion', 'STEM_DATA',
                                'morphgnt_lexicon.yaml')
            with open(path, 'r', encoding='utf-8') as f:
                _STEMS_DB = yaml.safe_load(f)
        except Exception:
            _STEMS_DB = {}
    return _STEMS_DB


def is_real_compound(lemma):
    """A lemma is a real compound verb if removing a prefix leaves a
    known simplex verb lemma. Returns (True, prefix) or (False, None)."""
    stems = get_stems_db()
    if not stems:
        return False, None
    lemma_na = na(lemma)
    lemma_keys_na = {na(k): k for k in stems}
    for pf in sorted(KNOWN_PREFIXES, key=len, reverse=True):
        pf_na = na(pf)
        if lemma_na.startswith(pf_na) and len(lemma_na) > len(pf_na):
            rest_na = lemma_na[len(pf_na):]
            if rest_na in lemma_keys_na:
                return True, pf
    return False, None


# ═══════════════════════════════════════════
# REFERENCE DATA
# ═══════════════════════════════════════════

# Known preposition prefixes (same as in morpheus.py — used to detect compounds)
KNOWN_PREFIXES = {
    'προσ','ἀντι','ἀνθ','ἀπο','ἀπ','ἀφ','ἀνα','ἀν','δια','δι',
    'εἰσ','εἰς','ἐκ','ἐξ','ἐμ','ἐν','ἐγ','ἐπι','ἐπ','ἐφ',
    'κατα','κατ','καθ','μετα','μετ','μεθ','παρα','παρ','περι',
    'προ','συγ','συλ','συμ','συν','συσ','ὑπερ','ὑπο','ὑπ',
}

# Suppletive verbs and vowel-initial verbs where the augment is
# effectively invisible in the surface form (aorist/imperfect stem
# already starts with a vowel that doesn't visibly lengthen)
SUPPLETIVE_AUG_OK = {
    'εἰμί', 'ἔχω', 'ὁράω', 'λέγω', 'φέρω', 'αἱρέω',
    'ἐσθίω', 'πίνω', 'ἔρχομαι', 'ἐργάζομαι', 'φημί',
    'εὑρίσκω',     # εὗρον — augment merged with initial εὑ-
    'ὑψόω',        # ὕψωσεν — υ→ῡ invisible
    'δύναμαι',     # ἠδυνήθην / ἐδυνήθην — irregular
    'ἵστημι',      # εἱστήκειν — augment + reduplication merged
    'ἀνοίγω',      # ἤνοιξα / ἀνέῳξα — irregular double augment forms
    # Compound verbs with ι-initial or η-initial stems where the temporal
    # augment is invisible (ι→ῑ, η→η, ω→ω all written the same)
    'ἐνισχύω',     # ἐνίσχυσεν — ι→ῑ invisible
    'ἐξίστημι',    # ἐξίσταντο — ι→ῑ invisible
    'διηγέομαι',   # διηγήσατο — η→η invisible
    'ἀνθίστημι',   # ἀνθίστατο — ι→ῑ invisible
    'συζητέω',     # συνεζήτει — σύν+ζητέω with complete ν-drop in lemma
    'ἐπαίρω',      # ἐπήρθη — compound with irregular αι→η augment
    'ἔξειμι',      # ἐξῄεσαν — -μι verb with irregular augment pattern
    'εὐαγγελίζω',  # εὐηγγελίζετο — εὖ+ἀγγελ with η inserted
    'καταφέρω',    # κατήνεγκα — suppletive aorist ἤνεγκα with compound
}

# Known 2nd-perfect / irregular perfect verbs that don't use κα formative.
# Extended 2026-04-17 via lexicon scan of greek-inflexion 4-/4+ stems —
# adding -έρχομαι, -ίστημι, -λαμβάνω compounds and root perfects that
# Acts-only testing didn't stress.
PERFECT_WITHOUT_KAPPA = {
    'οἶδα', 'ἔοικα', 'γίνομαι', 'πάσχω', 'πείθω',
    'λαμβάνω', 'ἵστημι',  # ἕστηκα is 2nd perfect
    # Pre-scale additions:
    'ἀκούω', 'γράφω', 'ἀπόλλυμι', 'εἴωθα', 'σήπω', 'σύνοιδα',
    'ἔρχομαι', 'εἰσέρχομαι', 'ἐξέρχομαι', 'ἀπέρχομαι', 'διέρχομαι',
    'παρέρχομαι', 'προσέρχομαι', 'συνέρχομαι',
    'ἐνίστημι', 'ἐφίστημι', 'συνίστημι', 'προΐστημι', 'περιΐστημι',
    'καταλαμβάνω', 'συλλαμβάνω', 'προγίνομαι',
}

# Verbs that take root aorists (no σα formative).
# Extended via lexicon scan for {2nd}/{root} YAML markers.
ROOT_AORIST_LEMMAS = {
    'τίθημι', 'δίδωμι', 'ἵημι', 'γινώσκω', 'βαίνω',
    'λαμβάνω', 'λέγω', 'ὁράω', 'ἐσθίω', 'πίνω', 'ἔρχομαι',
    'πίπτω', 'εὑρίσκω', 'φεύγω', 'ἔχω', 'τρέχω', 'ἄγω',
    'βάλλω', 'λείπω', 'τυγχάνω', 'μανθάνω',
    'ἁμαρτάνω', 'πάσχω', 'γίνομαι', 'ἵστημι', 'φημί',
    'αἱρέω', 'ἀποθνῄσκω', 'λαγχάνω',
    # Pre-scale additions:
    'θιγγάνω', 'κάμνω', 'λανθάνω', 'πυνθάνομαι', 'τίκτω',
    'δύνω', 'δείκνυμι', 'ῥήγνυμι',
    'ἀφικνέομαι', 'ἐφικνέομαι', 'καθαιρέω',
    # -έρχομαι compounds inherit root-aorist from ἔρχομαι:
    'εἰσέρχομαι', 'ἐξέρχομαι', 'προέρχομαι', 'παρέρχομαι',
    'κατέρχομαι', 'συνέρχομαι', 'ἀπέρχομαι', 'ἐπέρχομαι',
    'περιέρχομαι', 'ἀνέρχομαι',
    # -ἐσθίω / -λαμβάνω / -δίδωμι compounds likewise:
    'συνεσθίω', 'καταλείπω', 'παραλαμβάνω', 'προσλαμβάνω',
    'παραδίδωμι',
}
# Also add known compounds via prefix matching

VALID_MORPH_ROLES = {'pfx','aug','rdp','stm','frm','pmk','ve','suf'}
VALID_PTC_ROLES = {'marker'}
VALID_CASE_ROLES = {'n','g','d','a','v'}

# ═══════════════════════════════════════════
# FINDINGS COLLECTOR
# ═══════════════════════════════════════════

class Report:
    def __init__(self):
        self.findings = defaultdict(list)  # category -> list of findings
        self.stats = defaultdict(lambda: {'ok': 0, 'flag': 0})

    def flag(self, category, ref, form, detail):
        self.findings[category].append((ref, form, detail))

    def tally(self, category, ok):
        if ok:
            self.stats[category]['ok'] += 1
        else:
            self.stats[category]['flag'] += 1


# ═══════════════════════════════════════════
# RULE CHECKS
# ═══════════════════════════════════════════

def check_segs_concat(entry, report):
    """Segs concatenation should equal the word's surface form (minus editorial marks)."""
    segs = entry.get('segs', [])
    if not segs:
        return
    concat = ''.join(s.get('t', '') for s in segs)
    surface = strip_punct(entry.get('txt', ''))
    # Additional normalization: both sides should be accent-preserving but punct-stripped
    if na(concat) != na(surface):
        report.flag('SEGS_CONCAT_MISMATCH',
                    entry.get('ref', '?'),
                    entry.get('txt', ''),
                    f'segs concat="{concat}" vs surface="{surface}"')


def check_channel_vocab(entry, report):
    """All channel roles should be from known vocabularies."""
    for seg in entry.get('segs', []):
        ch = seg.get('ch', {})
        if 'morph' in ch and ch['morph'] not in VALID_MORPH_ROLES:
            report.flag('UNKNOWN_MORPH_ROLE',
                        entry.get('ref', '?'), entry.get('txt', ''),
                        f'morph role "{ch["morph"]}" on segment "{seg.get("t","")}"')
        if 'ptc' in ch and ch['ptc'] not in VALID_PTC_ROLES:
            report.flag('UNKNOWN_PTC_ROLE',
                        entry.get('ref', '?'), entry.get('txt', ''),
                        f'ptc role "{ch["ptc"]}" on segment "{seg.get("t","")}"')
        if 'case' in ch and ch['case'] not in VALID_CASE_ROLES:
            report.flag('UNKNOWN_CASE_ROLE',
                        entry.get('ref', '?'), entry.get('txt', ''),
                        f'case role "{ch["case"]}" on segment "{seg.get("t","")}"')


def check_augment_expected(entry, report):
    """Aorist/imperfect/pluperfect indicatives should have an augment."""
    prs = entry.get('prs', '')
    if 'verb' not in prs or 'ind' not in prs:
        return
    has_past = any(t in prs for t in [' aor ', ' impf ', ' plpf '])
    if not has_past:
        return
    has_aug = 'aug' in entry
    # Filter: suppletive verbs often have invisible augments
    lemma = entry.get('lem', '')
    if lemma in SUPPLETIVE_AUG_OK:
        report.tally('AUGMENT_EXPECTED', True)
        return
    report.tally('AUGMENT_EXPECTED', has_aug)
    if not has_aug:
        report.flag('AUGMENT_MISSING',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'{prs} lemma={lemma} — augment expected but not extracted')


def check_participle_structure(entry, report):
    """Participles should have case and a pmk (participle morpheme kernel)."""
    prs = entry.get('prs', '')
    if 'verb' not in prs or 'ptc' not in prs:
        return

    has_cs = 'cs' in entry
    has_pmk = 'ptc' in entry  # legacy key
    has_segs_marker = any(s.get('ch', {}).get('ptc') == 'marker'
                         for s in entry.get('segs', []))

    report.tally('PARTICIPLE_HAS_CASE', has_cs)
    report.tally('PARTICIPLE_HAS_MARKER', has_pmk and has_segs_marker)

    if not has_cs:
        report.flag('PARTICIPLE_NO_CASE',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'{prs} — participle missing case')
    if not has_pmk:
        report.flag('PARTICIPLE_NO_MARKER',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'{prs} — no pmk extracted')
    elif not has_segs_marker:
        report.flag('PARTICIPLE_MARKER_NOT_IN_SEGS',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'pmk="{entry.get("ptc","")}" but no p-marker segment')


def check_nominal_suffix(entry, report):
    """Nouns/adjectives/pronouns with case should have a suffix split
    (unless they're legitimately indeclinable)."""
    prs = entry.get('prs', '')
    if not any(p in prs for p in ['noun', 'adj', 'pers.pron', 'rel.pron', 'dem.pron', 'inter.pron']):
        return

    has_cs = 'cs' in entry
    has_suf = 'suf' in entry

    report.tally('NOMINAL_HAS_SUFFIX', has_suf)

    # Known indeclinable proper names — whole-word color expected
    INDECL_NAMES = {
        'Ἰερουσαλήμ', 'Ἰσραήλ', 'Ἀβραάμ', 'Δαυίδ', 'Μωϋσῆς',
        'Μωϋσεύς', 'Ἰακώβ', 'Ἰωσήφ', 'Σαούλ', 'Συμεών', 'Νίγερ',
        'Μαναήν', 'Χανάαν', 'Σαμουήλ', 'Βενιαμίν', 'Ἰεσσαί',
        'Κίς', 'Ἀαρών', 'Εὕα', 'Ἰσαάκ', 'Ἰακώβ', 'Δορκάς',
        'Ταβιθά', 'Ἁγαβος', 'Ἀδάμ', 'Σαλά', 'Σαλμών',
    }
    # Also: 3rd-decl consonant-stem nominatives that are legitimately bare
    BARE_STEM_FORMS = {
        ('χείρ', 'n'), ('φῶς', 'n'), ('φῶς', 'a'),
        ('γυνή', 'n'), ('ἀνήρ', 'n'), ('ὕδωρ', 'n'),
    }

    lemma = entry.get('lem', '')
    if lemma in INDECL_NAMES:
        return  # expected no suffix
    if (lemma, entry.get('cs', '')) in BARE_STEM_FORMS:
        return

    if has_cs and not has_suf:
        report.flag('NOMINAL_SUFFIX_UNSPLIT',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'{prs} lemma={lemma} — suffix split failed')


def check_compound_prefix(entry, report):
    """Verbs whose lemma is a genuine compound (prefix + known simplex lemma)
    should have a pfx extracted. Uses the stems DB to distinguish real
    compounds from simplex verbs that happen to start with prefix-letters."""
    prs = entry.get('prs', '')
    if 'verb' not in prs:
        return
    lemma = entry.get('lem', '')
    if not lemma:
        return

    is_compound, matched_prefix = is_real_compound(lemma)
    if not is_compound:
        return

    has_pfx = 'pfx' in entry
    report.tally('COMPOUND_PREFIX_EXTRACTED', has_pfx)

    if not has_pfx:
        report.flag('COMPOUND_PREFIX_MISSING',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'lemma={lemma} ({matched_prefix}+simplex) but no pfx extracted')


def _stem_has_sigmatic_aorist(lemma):
    """Check DB: does this verb's aorist stem end in σ/κ/ψ/ξ (sigmatic aorist)?
    If not, it's a liquid/nasal/root aorist with no extractable formative.
    Returns False if the verb has a {root} aorist variant (some forms use the
    root, others use the sigmatic — either is acceptable)."""
    stems = get_stems_db()
    entry = stems.get(lemma)
    if not entry:
        return None  # unknown
    v_stems = entry.get('stems', {})
    raw = v_stems.get('3-') or v_stems.get('3+', '')
    if not raw:
        return None
    # If the DB marks this as having a root aorist variant, the form might
    # legitimately be built on the root stem (no formative). Skip.
    if '{root}' in raw or '{2nd}' in raw:
        return False
    # Clean tags and slash variants
    aor_stem = re.sub(r'\{[^}]*\}', '', raw)
    if '/' in aor_stem:
        # If any variant is root-marked, skip the check
        variants = aor_stem.split('/')
        aor_stem = variants[0]
    last = na(aor_stem[-1:])
    return last in set('σκψξ')


def _stem_has_sigmatic_passive(lemma):
    """Check DB: does this verb's aorist passive stem contain θ?"""
    stems = get_stems_db()
    entry = stems.get(lemma)
    if not entry:
        return None
    v_stems = entry.get('stems', {})
    pass_stem = v_stems.get('6-') or v_stems.get('6+', '')
    pass_stem = re.sub(r'\{[^}]*\}', '', pass_stem)
    if '/' in pass_stem:
        pass_stem = pass_stem.split('/')[0]
    if not pass_stem:
        return None
    return 'θ' in na(pass_stem)


def _stem_has_kappa_perfect(lemma):
    """Check DB: does this verb's perfect active stem end in κ?"""
    stems = get_stems_db()
    entry = stems.get(lemma)
    if not entry:
        return None
    v_stems = entry.get('stems', {})
    perf_stem = v_stems.get('4-') or v_stems.get('4+', '')
    perf_stem = re.sub(r'\{[^}]*\}', '', perf_stem)
    if '/' in perf_stem:
        perf_stem = perf_stem.split('/')[0]
    if not perf_stem:
        return None
    return na(perf_stem[-1:]) == 'κ'


def check_formative_expected(entry, report):
    """Verbs in specific tense/voice combos should have formatives,
    but only when the DB confirms the verb uses a sigmatic/thematic pattern."""
    prs = entry.get('prs', '')
    if 'verb' not in prs:
        return

    has_frm = 'frm' in entry
    lemma = entry.get('lem', '')

    # 1st aorist active/middle: expect formative only if DB says aor stem is sigmatic
    if 'aor' in prs and ('act' in prs or 'mid' in prs):
        is_sigmatic = _stem_has_sigmatic_aorist(lemma)
        if is_sigmatic is False:
            # Liquid/root/nasal aorist — no formative expected
            return
        if is_sigmatic is None:
            return  # unknown verb, skip
        report.tally('AOR_ACT_FORMATIVE', has_frm)
        if not has_frm:
            report.flag('AOR_ACT_NO_FORMATIVE',
                        entry.get('ref', '?'), entry.get('txt', ''),
                        f'{prs} lemma={lemma} — σα/σε formative expected (sigmatic)')

    # Aorist passive: expect θ formative if DB says pass stem contains θ
    elif 'aor' in prs and 'pass' in prs:
        has_theta = _stem_has_sigmatic_passive(lemma)
        if has_theta is False or has_theta is None:
            return
        report.tally('AOR_PASS_FORMATIVE', has_frm)
        if not has_frm:
            report.flag('AOR_PASS_NO_FORMATIVE',
                        entry.get('ref', '?'), entry.get('txt', ''),
                        f'{prs} lemma={lemma} — θη/θε formative expected')

    # Perfect active: expect κ formative if DB confirms κ-perfect
    elif 'perf' in prs and 'act' in prs:
        has_kappa = _stem_has_kappa_perfect(lemma)
        if has_kappa is False or has_kappa is None:
            return
        report.tally('PERF_ACT_FORMATIVE', has_frm)
        if not has_frm:
            report.flag('PERF_ACT_NO_FORMATIVE',
                        entry.get('ref', '?'), entry.get('txt', ''),
                        f'{prs} lemma={lemma} — κα/κε formative expected')


def check_voice_classification(entry, report):
    """Every verb should have its voice classifiable as act/mid/pass."""
    prs = entry.get('prs', '')
    if 'verb' not in prs:
        return
    has_voice = any(v in prs for v in [' act', ' mid', ' pass'])
    report.tally('VERB_HAS_VOICE', has_voice)
    if not has_voice:
        report.flag('VERB_NO_VOICE',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'prs="{prs}" — no voice extracted')


def check_render_path(entry, report):
    """Check that the renderer will take the correct path for this entry.

    The HTML render takes the 'indeclinable' shortcut when the entry has
    no structured segs AND no stm/pfx/aug. That shortcut emits raw text
    with no CSS classes — fine for particles, broken for anything that
    needs morphological styling.

    Rule: if an entry has segs with any channel roles, the renderer must
    take the decomposed path (which it does when hasStructure is true).
    This tallies consistency; the current renderer handles all cases
    correctly as long as segs are emitted with structure.
    """
    if 'v' in entry or 'br' in entry:
        return
    segs = entry.get('segs', [])
    has_structure = any(s.get('ch') and len(s['ch']) > 0 for s in segs)
    # Content word with no structure at all = potential render bug
    is_content = entry.get('prs', '') and not any(
        entry['prs'].startswith(p) for p in ('conj', 'prep', 'ptcl', 'adv', 'interj'))
    if is_content and not has_structure and not (
            entry.get('stm') or entry.get('pfx') or entry.get('aug')):
        report.tally('RENDER_PATH_OK', False)
        report.flag('RENDER_PATH_WRONG',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'content word "{entry.get("prs","")}" will render as indeclinable')
    else:
        report.tally('RENDER_PATH_OK', True)


def check_segs_present(entry, report):
    """Content words (nouns, verbs, adj, pronouns, articles) should have segs.
    Particles/preps/conjs/adverbs/interjections legitimately have no segs."""
    if 'v' in entry or 'br' in entry:
        return
    if not entry.get('txt'):
        return
    prs = entry.get('prs', '')
    # Skip non-content POS — they decompose to themselves
    SKIP_POS = ('conj', 'prep', 'ptcl', 'adv', 'interj')
    if any(prs.startswith(p) for p in SKIP_POS):
        return
    has_segs = bool(entry.get('segs'))
    report.tally('HAS_SEGS', has_segs)
    if not has_segs:
        report.flag('NO_SEGS',
                    entry.get('ref', '?'), entry.get('txt', ''),
                    f'prs="{prs}" — no segs emitted for content word')


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

ALL_CHECKS = [
    check_segs_concat,
    check_channel_vocab,
    check_augment_expected,
    check_participle_structure,
    check_nominal_suffix,
    check_compound_prefix,
    check_formative_expected,
    check_voice_classification,
    check_segs_present,
    check_render_path,
]


def validate(data):
    report = Report()
    for i, entry in enumerate(data.get('data', [])):
        # Skip structural markers
        if 'v' in entry or 'br' in entry:
            continue
        # Add a ref for reporting
        if 'ref' not in entry:
            entry['ref'] = f'idx{i}'
        for check in ALL_CHECKS:
            try:
                check(entry, report)
            except Exception as e:
                report.flag('VALIDATOR_ERROR', entry.get('ref', '?'),
                            entry.get('txt', ''), f'{check.__name__}: {e}')
    return report


def print_report(report, chapter_label):
    print(f'\n{"═"*60}')
    print(f'  Validation Report: {chapter_label}')
    print(f'{"═"*60}\n')

    # Coverage stats
    print('COVERAGE STATS (% ok):')
    for cat in sorted(report.stats.keys()):
        ok = report.stats[cat]['ok']
        flag = report.stats[cat]['flag']
        total = ok + flag
        if total == 0:
            continue
        pct = 100.0 * ok / total
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        print(f'  {cat:32s} {bar} {pct:5.1f}%  ({ok}/{total})')

    # Findings by category
    print('\nFINDINGS BY CATEGORY:\n')
    for cat in sorted(report.findings.keys()):
        items = report.findings[cat]
        print(f'  [{cat}]  {len(items)} instance(s)')
        for ref, form, detail in items[:10]:
            print(f'    {ref}  {form:22s}  {detail}')
        if len(items) > 10:
            print(f'    ... ({len(items) - 10} more)')
        print()


def main():
    if len(sys.argv) < 2:
        print('Usage: validate_chapter.py <chapter_data.json> [<chapter_data.json> ...]')
        sys.exit(1)

    for path in sys.argv[1:]:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        label = path.replace('_data.json', '').replace('./', '')
        # Add refs based on verse markers in the data stream
        current_verse = None
        chapter = data.get('chapter', '?')
        for entry in data.get('data', []):
            if 'v' in entry:
                current_verse = entry['v']
            else:
                entry['ref'] = f'{chapter}:{current_verse}'
        report = validate(data)
        print_report(report, label)


if __name__ == '__main__':
    main()
