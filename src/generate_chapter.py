#!/usr/bin/env python3
"""
Generate morpheme-decomposed JSON for a GNT chapter from MorphGNT data.
Uses stem data from greek-inflexion and glosses from morphological-lexicon.
"""
import json, re, sys, os
import yaml
from collections import defaultdict

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
STEMS_FILE = os.path.join(DATA, 'greek-inflexion', 'STEM_DATA', 'morphgnt_lexicon.yaml')
LEXEMES_FILE = os.path.join(DATA, 'morphological-lexicon', 'lexemes.yaml')
# Sense-line files live in the sibling readers-gnt repo. Absolute path
# works on Stan's machine; override via SENSE_LINES_DIR env var for
# other environments. Fallback to common repo layouts.
SENSE_LINES_DIR = os.environ.get(
    'SENSE_LINES_DIR',
    'C:/Users/bibleman/repos/readers-gnt/data/text-files/v4-editorial'
)

# Book registry — single source of truth for MorphGNT filenames + display names.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import BOOKS


def morphgnt_path_for(book_code):
    """Resolve a book code (e.g., 'acts', 'romans') to its MorphGNT file path."""
    if book_code not in BOOKS:
        raise ValueError(f'unknown book code: {book_code!r}; '
                         f'known: {sorted(BOOKS.keys())}')
    return os.path.join(DATA, 'morphgnt', BOOKS[book_code]['file'])

# ═══ LOAD DATA ═══

def load_morphgnt_chapter(book_file, chapter):
    """Load all words for a given chapter from MorphGNT."""
    ch_str = f'{chapter:02d}'
    words = []
    with open(book_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            ref = parts[0]  # e.g. 050901
            if ref[2:4] != ch_str:
                continue
            words.append({
                'ref': ref,
                'verse': int(ref[4:6]),
                'pos': parts[1],
                'parsing': parts[2],
                'text': parts[3],      # with punctuation
                'word': parts[4],      # without punctuation
                'norm': parts[5],      # normalized
                'lemma': parts[6],
            })
    return words

def load_stems():
    """Load verb stem data from greek-inflexion."""
    with open(STEMS_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_lexicon():
    """Load lexicon glosses."""
    with open(LEXEMES_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# ═══ NT FREQUENCY DATA ═══
# We'll compute from MorphGNT (full NT would be better, but Acts-only for now)
def load_nt_frequencies():
    """Count lemma frequencies across all MorphGNT books."""
    freq = defaultdict(int)
    gnt_dir = os.path.join(DATA, 'morphgnt')
    for fname in os.listdir(gnt_dir):
        if fname.endswith('-morphgnt.txt'):
            with open(os.path.join(gnt_dir, fname), 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 7:
                        freq[parts[6]] += 1
    return freq

# ═══ MORPHEME DECOMPOSITION ═══

# Known preposition prefixes for compound verbs
PREFIXES = [
    ('προσ', 'προσ'), ('ἀνθ', 'ἀντι'), ('ἀντι', 'ἀντι'),
    ('ἀπο', 'ἀπο'), ('ἀπ', 'ἀπο'), ('ἀφ', 'ἀπο'),
    ('ἀνα', 'ἀνα'), ('ἀν', 'ἀνα'),
    ('δια', 'δια'), ('δι', 'δια'),
    ('εἰσ', 'εἰσ'), ('εἰς', 'εἰσ'),
    ('ἐκ', 'ἐκ'), ('ἐξ', 'ἐκ'),
    ('ἐμ', 'ἐν'), ('ἐν', 'ἐν'), ('ἐγ', 'ἐν'),
    ('ἐπι', 'ἐπι'), ('ἐπ', 'ἐπι'), ('ἐφ', 'ἐπι'),
    ('κατα', 'κατα'), ('κατ', 'κατα'), ('καθ', 'κατα'),
    ('μετα', 'μετα'), ('μετ', 'μετα'), ('μεθ', 'μετα'),
    ('παρα', 'παρα'), ('παρ', 'παρα'),
    ('περι', 'περι'),
    ('προ', 'προ'),
    ('συγ', 'συν'), ('συλ', 'συν'), ('συμ', 'συν'), ('συν', 'συν'), ('συσ', 'συν'),
    ('ὑπερ', 'ὑπερ'),
    ('ὑπο', 'ὑπο'), ('ὑπ', 'ὑπο'),
]

# Augment patterns
def strip_augment(form, stem_unaug):
    """Try to identify the augment in a verb form."""
    # The augment is the difference between augmented and unaugmented stems
    # Common: ε- prefix, or lengthened initial vowel
    if not stem_unaug:
        return None, form
    # Simple ε-augment
    if form.startswith('ἐ') and not stem_unaug.startswith('ἐ'):
        return 'ἐ', form[1:]
    if form.startswith('ἠ') and stem_unaug.startswith('α'):
        return 'ἠ', form  # vowel lengthening augment
    if form.startswith('ἠ') and stem_unaug.startswith('ἐ'):
        return 'ἠ', form  # augmented ἐ -> ἠ
    if form.startswith('ηὐ') and stem_unaug.startswith('εὐ'):
        return 'η', form  # augmented εὐ -> ηὐ
    return None, form


def get_case_code(parsing):
    """Extract case from MorphGNT parsing code."""
    # Parsing: person, tense, voice, mood, case, number, gender, degree
    # Position 4 = case: N,G,D,A,V
    case_map = {'N': 'n', 'G': 'g', 'D': 'd', 'A': 'a', 'V': 'v'}
    if len(parsing) > 4:
        return case_map.get(parsing[4], None)
    return None


def get_tense_voice_mood(parsing):
    """Extract tense, voice, mood from parsing code."""
    if len(parsing) < 4:
        return None, None, None
    t = parsing[1] if parsing[1] != '-' else None  # P,I,F,A,X,Y
    v = parsing[2] if parsing[2] != '-' else None  # A,M,P
    m = parsing[3] if parsing[3] != '-' else None  # I,S,O,D,N,P
    return t, v, m


# Verb ending tables
VERB_ENDINGS_PRIMARY_ACT = {
    '1S': 'ω', '2S': 'εις', '3S': 'ει',
    '1P': 'ομεν', '2P': 'ετε', '3P': 'ουσι(ν)',
}

# Personal endings by tense/voice/mood
def identify_verb_ending(form, parsing, stem_data):
    """Try to split a verb form into stem + formative + ending."""
    t, v, m = get_tense_voice_mood(parsing)
    person = parsing[0] if parsing[0] != '-' else None
    number = parsing[5] if len(parsing) > 5 and parsing[5] != '-' else None

    # Known aorist markers
    if t == 'A' and v == 'A':
        # 1st aorist: σα
        if 'σ' in form:
            idx = form.rfind('σ')
            # Check for σα pattern
            pass

    return None, None, None


def decompose_word(word_data, stems_db, lexicon):
    """
    Decompose a single word into morpheme components.
    Returns dict with: pfx, aug, rdp, stm, frm, ve, suf, cs, txt, lem, prs
    """
    from morpheus import decompose_verb as morph_verb, decompose_nominal as morph_nominal

    text = word_data['text']
    lemma = word_data['lemma']
    pos = word_data['pos']
    parsing = word_data['parsing']

    result = {
        'txt': text,
        'lem': lemma,
        'prs': format_parsing(parsing, pos),
    }

    # ═══ INDECLINABLE / PARTICLES ═══
    if pos in ('C-', 'P-', 'X-', 'I-', 'D-'):
        return result

    # ═══ ARTICLE ═══
    if pos == 'RA':
        from morpheus import clean_surface
        cs = get_case_code(parsing)
        clean_text = clean_surface(text)
        if cs:
            result['stm'] = clean_text
            result['cs'] = cs
            # Articles are pure case/gender/number markers — treat the whole
            # word as a case suffix so the case layer colors them
            result['segs'] = [{'t': clean_text, 'ch': {'morph': 'suf', 'case': cs}}]
        else:
            result['segs'] = [{'t': clean_text, 'ch': {}}]
        return result

    # ═══ VERBS ═══
    if pos == 'V-':
        stems_dict = {}
        if lemma in stems_db and stems_db[lemma] and 'stems' in stems_db[lemma]:
            stems_dict = stems_db[lemma]['stems']
        morph = morph_verb(text, lemma, parsing, pos, stems_dict)
        result.update(morph)

        # Attach tense/voice/mood code (3-char) for the renderer.
        # Used by inflected-gloss lookup and other tvm-aware UX.
        if len(parsing) >= 4:
            result['tvm'] = parsing[1:4]

        # Pre-compute the inflected gloss for indicative-mood verbs
        # so the browser can just look it up. Non-indicative moods get
        # the bare gloss back (the inflect_gloss() function handles
        # this internally).
        from inflect_gloss import inflect_gloss
        bare = resolve_bare_gloss(lemma, lexicon)
        if bare:
            inflected = inflect_gloss(bare, result.get('tvm', ''), lemma)
            # Only emit igl when it differs from the bare gloss — saves
            # JSON bytes and signals "no inflection happened" to renderer.
            if inflected and inflected != bare:
                result['igl'] = inflected
        return result

    # ═══ NOUNS / ADJECTIVES / PRONOUNS ═══
    if pos in ('N-', 'A-', 'RR', 'RD', 'RI', 'RP'):
        morph = morph_nominal(text, parsing)
        result.update(morph)
        return result

    return result


def _clean_stem(s):
    """Strip {tags}, pipe delimiters, and take first slash variant."""
    if not s:
        return ''
    s = re.sub(r'\{[^}]*\}', '', s)
    s = s.replace('|', '')
    if '/' in s:
        s = s.split('/')[0]
    return s


def _detect_augment_between(aug_na, unaug_na):
    """Find the internal augment by comparing augmented vs unaugmented stems.
    Returns (prefix_len, augment_len_in_aug, augment_len_in_unaug) or None.
    The augment sits at position prefix_len in the augmented stem.
    """
    # Find the common prefix (the preposition prefix)
    i = 0
    while i < len(aug_na) and i < len(unaug_na) and aug_na[i] == unaug_na[i]:
        i += 1

    if i == 0:
        # Diverge at start — simple (non-compound) augment
        return None

    ar = aug_na[i:]
    ur = unaug_na[i:]

    # Syllabic augment: ε inserted
    if ar.startswith('ε') and not ur.startswith('ε') and ar[1:].startswith(ur):
        return (i, 1, 0)

    # Temporal augments at the prefix/stem boundary
    TEMPORAL = [
        ('η', 'α', 1, 1), ('η', 'ε', 1, 1), ('ω', 'ο', 1, 1),
        ('ηυ', 'ευ', 2, 2), ('ηυ', 'αυ', 2, 2),
        ('ῃ', 'αι', 1, 2), ('ῳ', 'οι', 1, 2),
        ('ει', 'ι', 2, 1), ('ει', 'ε', 2, 1),
    ]
    for aug_pat, unaug_pat, alen, ulen in TEMPORAL:
        if ar.startswith(aug_pat) and ur.startswith(unaug_pat):
            # Verify the rest matches
            if ar[alen:] == ur[ulen:] or ar[alen:].startswith(ur[ulen:]) or len(ar[alen:]) > 0:
                return (i, alen, ulen)

    return None


def decompose_verb(wd, stems_db, result):
    """Decompose a verb form into morphemes."""
    word = wd['norm']
    lemma = wd['lemma']
    parsing = wd['parsing']
    t, v, m = get_tense_voice_mood(parsing)
    person = parsing[0] if parsing[0] != '-' else None
    number = parsing[5] if len(parsing) > 5 and parsing[5] != '-' else None

    clean = re.sub(r'[⸀⸁⸂⸃⸄⸅²³¹]', '', wd['text']).strip('.,;·:?!')
    clean_lower = clean.lower()  # for case-insensitive matching

    # Get stems for this lemma
    stems = {}
    if lemma in stems_db and stems_db[lemma] and 'stems' in stems_db[lemma]:
        stems = stems_db[lemma]['stems']

    # ═══ DETERMINE STEM KEY ═══
    stem_key_map = {
        ('P', 'A'): '1-', ('P', 'M'): '1-', ('P', 'P'): '1-',
        ('I', 'A'): '1+', ('I', 'M'): '1+', ('I', 'P'): '1+',
        ('F', 'A'): '2-', ('F', 'M'): '2-',
        ('A', 'A'): '3-', ('A', 'M'): '3-',
        ('X', 'A'): '4-', ('Y', 'A'): '4+',
        ('X', 'M'): '5-', ('X', 'P'): '5-',
        ('Y', 'M'): '5+', ('Y', 'P'): '5+',
        ('A', 'P'): '6-', ('F', 'P'): '7-',
    }
    aug_key_map = {
        ('I', 'A'): ('1+', '1-'), ('I', 'M'): ('1+', '1-'), ('I', 'P'): ('1+', '1-'),
        ('A', 'A'): ('3+', '3-'), ('A', 'M'): ('3+', '3-'),
        ('Y', 'A'): ('4+', '4-'),
        ('Y', 'M'): ('5+', '5-'), ('Y', 'P'): ('5+', '5-'),
        ('A', 'P'): ('6+', '6-'),
    }

    stem_key = stem_key_map.get((t, v))
    stem_val = _clean_stem(stems.get(stem_key, '')) if stem_key else ''
    if not stem_val and stem_key and stem_key.endswith('-'):
        stem_val = _clean_stem(stems.get(stem_key[:-1] + '+', ''))

    # ═══ AUGMENT DETECTION ═══
    # Strategy: compare augmented vs unaugmented stems from DB.
    # For compound verbs, detect where they diverge internally.
    aug = None
    aug_pfx_len = 0  # length of prefix discovered via augment comparison

    aug_stem_key = aug_key_map.get((t, v))
    if aug_stem_key and m == 'I':  # augment only in indicative
        aug_val = _clean_stem(stems.get(aug_stem_key[0], ''))
        unaug_val = _clean_stem(stems.get(aug_stem_key[1], ''))

        if aug_val and unaug_val and aug_val != unaug_val:
            av_na = strip_accents(aug_val)
            uv_na = strip_accents(unaug_val)

            # Try compound augment detection first (internal augment)
            compound = _detect_augment_between(av_na, uv_na)
            if compound:
                pfx_len, aug_len_aug, aug_len_unaug = compound
                # Extract the actual augment characters from the augmented stem
                aug = aug_val[pfx_len:pfx_len + aug_len_aug]
                aug_pfx_len = pfx_len
            else:
                # Simple (word-initial) augment
                if av_na.startswith('ε') and not uv_na.startswith('ε'):
                    aug = 'ἐ'
                elif av_na.startswith('η') and uv_na.startswith('α'):
                    aug = 'ἠ'
                elif av_na.startswith('η') and uv_na.startswith('ε'):
                    aug = 'ἠ'
                elif av_na.startswith('ηυ') and uv_na.startswith('ευ'):
                    aug = 'ηὐ'
                elif av_na.startswith('ει') and uv_na.startswith('ι'):
                    aug = 'εἰ'
                elif av_na.startswith('ει') and uv_na.startswith('ε') and not uv_na.startswith('ει'):
                    aug = 'εἰ'
                elif av_na.startswith('ε') and uv_na.startswith('ε'):
                    pass  # no visible augment change
                elif len(av_na) > len(uv_na):
                    aug = 'ἐ'

        # Suppletive verbs where DB can't distinguish aug/unaug
        if not aug:
            _SUPP = {
                'λέγω':    {('A','A'): 'εἶ', ('A','M'): 'εἶ'},
                'ὁράω':    {('A','A'): 'εἶ'},
                'φέρω':    {('A','A'): 'ἤ'},
                'αἱρέω':   {('A','A'): 'εἷ'},
                'ἐσθίω':   {('A','A'): 'ἔ'},
                'πίνω':    {('A','A'): 'ἔ'},
                'ἔρχομαι': {('A','A'): 'ἦ', ('A','M'): 'ἦ'},
                'ἔχω':     {('I','A'): 'εἶ'},
                'ἐργάζομαι': {('A','M'): 'ἠ', ('A','P'): 'ἠ'},
            }
            sup = _SUPP.get(lemma, {})
            if (t, v) in sup:
                aug = sup[(t, v)]

        # Use augmented stem for matching
        if aug_val:
            stem_val = aug_val

    # ═══ PREFIX + STEM MATCHING ═══
    # For compound verbs with internal augment, we know the prefix length
    # from the augment comparison. Otherwise, detect prefix from PREFIXES list.
    pfx = ''
    remaining = clean

    if aug_pfx_len > 0:
        # We know exactly where the prefix ends from augment detection
        pfx = clean[:aug_pfx_len]
        remaining = clean[aug_pfx_len:]
    elif stem_val:
        # Detect prefix by comparing surface form to stem
        stem_na = strip_accents(stem_val).lower()
        for pf, canonical in sorted(PREFIXES, key=lambda x: -len(x[0])):
            clean_na = strip_accents(clean).lower()
            if clean_na.startswith(pf) and not stem_na.startswith(pf):
                pfx = clean[:len(pf)]
                remaining = clean[len(pf):]
                break

    # Match the stem against remaining text (case + accent insensitive)
    stem_text = ''
    rest = ''
    if stem_val:
        match_stem = stem_val
        # Strip prefix from stem_val if the stem includes it
        if pfx and aug_pfx_len > 0:
            match_na = strip_accents(match_stem).lower()
            pfx_na = strip_accents(pfx).lower()
            if match_na.startswith(pfx_na):
                match_stem = match_stem[len(pfx):]

        ms_na = strip_accents(match_stem).lower()
        rem_na = strip_accents(remaining).lower()

        if rem_na.startswith(ms_na):
            stem_text = remaining[:len(match_stem)]
            rest = remaining[len(match_stem):]
        else:
            # Fallback: whole remaining is stem
            stem_text = remaining
            rest = ''
    else:
        stem_text = remaining
        rest = ''

    # ═══ SPLIT AUGMENT FROM STEM ═══
    if aug:
        aug_na = strip_accents(aug).lower()
        stem_na = strip_accents(stem_text).lower()
        if stem_na.startswith(aug_na):
            aug = stem_text[:len(aug)]
            stem_text = stem_text[len(aug):]
        else:
            # Augment detected but can't find it in stem — keep it anyway
            # (this handles capital-initial forms like Ἐγένετο)
            if len(stem_text) >= len(aug):
                # Check if first chars match after case folding
                first_na = strip_accents(stem_text[:len(aug)]).lower()
                if first_na == aug_na:
                    aug = stem_text[:len(aug)]
                    stem_text = stem_text[len(aug):]
                else:
                    aug = None
            else:
                aug = None

    # ═══ EXTRACT TENSE FORMATIVE FROM STEM ═══
    formative = ''
    present_stem = _clean_stem(stems.get('1-', ''))

    if present_stem and stem_text and t and t not in ('P',):
        # Strip augment from stem_text for comparison
        cmp_stem = stem_text

        ps_na = strip_accents(present_stem)
        cs_na = strip_accents(cmp_stem)

        # Known formative patterns to extract from the end of the tense stem
        formative_extracted = ''

        if t == 'A' and v in ('A', 'M'):
            # 1st aorist: σ formative (or ψ/ξ from consonant fusion)
            if cs_na.endswith('σ') and not ps_na.endswith('σ'):
                formative_extracted = cmp_stem[-1]
            elif len(cs_na) > len(ps_na) and cs_na.endswith('σ'):
                formative_extracted = cmp_stem[-1]
            elif cs_na.endswith('ψ') and ps_na[-1:] in ('π','β','φ'):
                formative_extracted = cmp_stem[-1]  # labial + σ = ψ
            elif cs_na.endswith('ξ') and ps_na[-1:] in ('κ','γ','χ'):
                formative_extracted = cmp_stem[-1]  # velar + σ = ξ
            # κ-aorist (-μι verbs)
            elif cs_na.endswith('κ') and not ps_na.endswith('κ'):
                formative_extracted = cmp_stem[-1]

        elif t == 'A' and v == 'P':
            # Aorist passive: θ marker
            if cs_na.endswith('θ'):
                formative_extracted = cmp_stem[-1]

        elif t == 'F' and v in ('A', 'M'):
            # Future: σ (or ψ/ξ fusion)
            if cs_na.endswith('σ') and not ps_na.endswith('σ'):
                formative_extracted = cmp_stem[-1]
            elif cs_na.endswith('ψ') and ps_na[-1:] in ('π','β','φ'):
                formative_extracted = cmp_stem[-1]
            elif cs_na.endswith('ξ') and ps_na[-1:] in ('κ','γ','χ'):
                formative_extracted = cmp_stem[-1]

        elif t == 'F' and v == 'P':
            # Future passive: θησ
            if cs_na.endswith('θησ'):
                formative_extracted = cmp_stem[-3:]

        elif t == 'X' and v == 'A':
            # Perfect active: κ formative
            if cs_na.endswith('κ') and not ps_na.endswith('κ'):
                formative_extracted = cmp_stem[-1]

        if formative_extracted:
            stem_text = cmp_stem[:-len(formative_extracted)]
            formative = formative_extracted

    # Bug 4 fix: fallback formative detection by pattern when pp1 is missing
    if not formative and not present_stem and stem_text and t:
        cs_na = strip_accents(stem_text)
        if t == 'A' and v in ('A', 'M'):
            if cs_na.endswith('σ'):
                formative = stem_text[-1]; stem_text = stem_text[:-1]
            elif cs_na.endswith('ψ') or cs_na.endswith('ξ'):
                formative = stem_text[-1]; stem_text = stem_text[:-1]
        elif t == 'A' and v == 'P':
            if cs_na.endswith('θ'):
                formative = stem_text[-1]; stem_text = stem_text[:-1]
        elif t == 'F' and v in ('A', 'M'):
            if cs_na.endswith('σ') or cs_na.endswith('ψ') or cs_na.endswith('ξ'):
                formative = stem_text[-1]; stem_text = stem_text[:-1]
        elif t == 'F' and v == 'P':
            if cs_na.endswith('θησ'):
                formative = stem_text[-3:]; stem_text = stem_text[:-3]
        elif t == 'X' and v == 'A':
            if cs_na.endswith('κ'):
                formative = stem_text[-1]; stem_text = stem_text[:-1]

    # ═══ DETECT REDUPLICATION ══���
    rdp = ''
    if t in ('X', 'Y'):  # perfect/pluperfect
        # Common reduplication: first consonant + ε
        if len(stem_text) >= 2 and stem_text[1] == 'ε':
            first_char_na = strip_accents(stem_text[0])
            present_start_na = strip_accents(present_stem[0]) if present_stem else ''
            if first_char_na == present_start_na:
                rdp = stem_text[:2]
                stem_text = stem_text[2:]

    # ═══ SPLIT REST INTO FORMATIVE SUFFIX + ENDING ═══
    # For aorist passive, the θη/θε in 'rest' is part of the formative
    if not formative and rest:
        if t == 'A' and v == 'P':
            if rest.startswith('η') or rest.startswith('ή'):
                formative = (formative or '') + rest[0]
                rest = rest[1:]
            elif rest.startswith('ε'):
                formative = (formative or '') + rest[0]
                rest = rest[1:]

    ending = rest

    # Build result
    if pfx:
        result['pfx'] = pfx
    if aug:
        result['aug'] = aug
    if rdp:
        result['rdp'] = rdp
    if stem_text:
        result['stm'] = stem_text
    if formative:
        result['frm'] = formative
    if ending:
        result['ve'] = ending

    # For participles, also add case
    if m == 'P':
        cs = get_case_code(parsing)
        if cs:
            result['cs'] = cs
            # Reclassify the ending as a case suffix for participles
            if ending:
                result['suf'] = ending
                if 've' in result:
                    del result['ve']

    return result


def split_formative_ending(rest, t, v, m, person, number):
    """Split the post-stem portion into formative (tense marker) and ending."""
    if not rest:
        return '', ''

    # ═══ AORIST ═══
    if t == 'A':
        if v in ('A', 'M'):
            # 1st aorist: σα + ending
            if rest.startswith('σ'):
                # σα-aorist
                if m == 'N':  # infinitive
                    return 'σ', rest[1:]  # σαι
                if m == 'P':  # participle
                    return 'σ', rest[1:]
                # Find where σα ends
                if len(rest) >= 2 and rest[1] in 'αάᾶ':
                    return rest[:2], rest[2:]  # σα + ending
                return 'σ', rest[1:]
            # κα-aorist (for -μι verbs)
            if rest.startswith('κ'):
                if len(rest) >= 2:
                    return rest[:2], rest[2:]
                return rest, ''
            # 2nd aorist - thematic, ending only
            return '', rest
        if v == 'P':
            # Aorist passive: θη/θε + ending
            if rest.startswith('θη') or rest.startswith('θή'):
                return rest[:2], rest[2:]
            if rest.startswith('θε'):
                return rest[:2], rest[2:]
            return '', rest

    # ═══ IMPERFECT ═══
    if t == 'I':
        return '', rest  # no formative, just secondary endings

    # ═══ PRESENT ═══
    if t == 'P':
        return '', rest  # primary endings directly on stem

    # ═══ FUTURE ═══
    if t == 'F':
        if rest.startswith('σ'):
            return 'σ', rest[1:]
        if v == 'P' and rest.startswith('θησ'):
            return 'θησ', rest[3:]
        return '', rest

    # ═══ PERFECT ═══
    if t in ('X', 'Y'):
        if v == 'A' and rest.startswith('κ'):
            return 'κ', rest[1:]
        return '', rest

    return '', rest


def decompose_nominal(wd, result):
    """Decompose a noun/adjective/pronoun into stem + case ending."""
    word = wd['norm']
    clean = re.sub(r'[⸀⸁⸂⸃⸄⸅²³¹]', '', wd['text']).strip('.,;·:?!')
    parsing = wd['parsing']
    cs = get_case_code(parsing)

    # Common noun/adj endings by declension
    # We'll use a simple suffix-stripping approach
    number = parsing[5] if len(parsing) > 5 else '-'

    # Known endings (most common)
    endings_map = {
        # 1st declension
        ('n', 'S'): ['ος', 'ον', 'α', 'η', 'ης', 'ας'],
        ('g', 'S'): ['ου', 'ης', 'ας', 'ων', 'εως', 'ους'],
        ('d', 'S'): ['ῳ', 'ῷ', 'ᾳ', 'ῃ', 'ει', 'ϊ', 'ι'],
        ('a', 'S'): ['ον', 'ην', 'αν', 'α', 'ιν', 'υν', 'ν', 'ος'],
        ('v', 'S'): ['ε', 'η', 'α', 'ου', 'ι', 'υ', 'ος'],
        ('n', 'P'): ['οι', 'αι', 'α', 'ες', 'εις', 'η'],
        ('g', 'P'): ['ων', 'ῶν'],
        ('d', 'P'): ['οις', 'αις', 'σι', 'σιν', 'σί', 'εσι', 'εσιν', 'ψι', 'ψιν', 'ξι', 'ξιν'],
        ('a', 'P'): ['ους', 'ας', 'α', 'εις', 'ης', 'η'],
        ('v', 'P'): ['οι', 'αι', 'ες', 'α'],
    }

    if cs and number:
        endings = endings_map.get((cs, number), [])
        for end in sorted(endings, key=len, reverse=True):
            if clean.endswith(end) and len(clean) > len(end):
                stem = clean[:-len(end)]
                result['stm'] = stem
                result['suf'] = end
                result['cs'] = cs
                return result

    # Fallback: whole word is stem
    result['stm'] = clean
    if cs:
        result['cs'] = cs
    return result


def strip_accents(s):
    """Strip Greek accents for comparison. Simple version."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def format_parsing(parsing, pos):
    """Convert MorphGNT parsing code to human-readable string.

    Display order by word class (Stan's preferred order, 2026-04-17):
      • Finite verb:   tense voice mood person number
      • Participle:    tense voice ptc case number gender
      • Infinitive:    tense voice inf
      • Nominal:       pos case number gender

    The 'ptc' mood label is preserved (not "ptcpl") so the template's
    isPtc regex (/\\bptc\\b/) keeps working.
    """
    pos_names = {
        'N-': 'noun', 'V-': 'verb', 'A-': 'adj', 'RA': 'art',
        'C-': 'conj', 'P-': 'prep', 'D-': 'adv', 'X-': 'ptcl',
        'RP': 'pers.pron', 'RR': 'rel.pron', 'RD': 'dem.pron',
        'RI': 'inter.pron', 'I-': 'interj',
    }

    persons = {'1': '1', '2': '2', '3': '3'}
    tenses = {'P': 'pres', 'I': 'impf', 'F': 'fut', 'A': 'aor', 'X': 'perf', 'Y': 'plpf'}
    voices = {'A': 'act', 'M': 'mid', 'P': 'pass'}
    moods = {'I': 'ind', 'S': 'subj', 'O': 'opt', 'D': 'imp', 'N': 'inf', 'P': 'ptc'}
    cases = {'N': 'nom', 'G': 'gen', 'D': 'dat', 'A': 'acc', 'V': 'voc'}
    numbers = {'S': 'sg', 'P': 'pl'}
    genders = {'M': 'masc', 'F': 'fem', 'N': 'neut'}

    # Verbs have their own display order based on mood
    if pos == 'V-':
        mood = parsing[3]
        parts = []
        if parsing[1] in tenses: parts.append(tenses[parsing[1]])
        if parsing[2] in voices: parts.append(voices[parsing[2]])
        if mood in moods: parts.append(moods[mood])

        if mood == 'P':  # participle: + case number gender
            if parsing[4] in cases: parts.append(cases[parsing[4]])
            if parsing[5] in numbers: parts.append(numbers[parsing[5]])
            if parsing[6] in genders: parts.append(genders[parsing[6]])
        elif mood == 'N':  # infinitive: stops at mood
            pass
        else:  # finite (ind, subj, opt, imp): + person number
            if parsing[0] in persons: parts.append(persons[parsing[0]])
            if parsing[5] in numbers: parts.append(numbers[parsing[5]])

        return ' '.join(parts)

    # Nominals and everything else: pos-first then agreement features
    parts = [pos_names.get(pos, pos)]
    if parsing[4] in cases: parts.append(cases[parsing[4]])
    if parsing[5] in numbers: parts.append(numbers[parsing[5]])
    if parsing[6] in genders: parts.append(genders[parsing[6]])
    return ' '.join(parts)


def get_freq_band(freq):
    """Return frequency band for gloss display."""
    if freq <= 1:
        return 1
    elif freq <= 10:
        return 10
    elif freq <= 20:
        return 20
    elif freq <= 40:
        return 40
    else:
        return None  # too common, no gloss needed


def load_sense_lines(book_code, chapter):
    """Load sense-line file and return structured layout.
    Returns a list of: {'verse': N} for verse markers,
                       {'br': True} for line breaks,
                       {'word': 'text'} for words to match against MorphGNT.

    readers-gnt uses short codes (rom, 1cor, heb) in directory names
    and file prefixes. Translate from our canonical code via
    books.py's sense_code field.
    """
    sense_code = BOOKS.get(book_code, {}).get('sense_code', book_code)

    # Map short sense-codes to their NN-<code> directories
    book_dirs = {}
    if os.path.isdir(SENSE_LINES_DIR):
        for d in os.listdir(SENSE_LINES_DIR):
            parts = d.split('-', 1)
            if len(parts) == 2:
                book_dirs[parts[1]] = d

    dir_name = book_dirs.get(sense_code)
    if not dir_name:
        return None

    ch_str = f'{chapter:02d}'
    # Files are named e.g. rom-03.txt, acts-09.txt (short code)
    ch_file = os.path.join(SENSE_LINES_DIR, dir_name, f'{sense_code}-{ch_str}.txt')
    if not os.path.exists(ch_file):
        return None

    layout = []
    with open(ch_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            stripped = line.strip()

            # Blank line = verse separator (paragraph break)
            if not stripped:
                layout.append({'gap': True})
                continue

            # Verse reference like "9:1"
            m = re.match(r'^(\d+):(\d+)$', stripped)
            if m:
                layout.append({'verse': int(m.group(2))})
                continue

            # Sense line — extract individual words
            words_in_line = stripped.split()
            for w in words_in_line:
                layout.append({'word': w})
            layout.append({'br': True})  # line break after each sense line

    return layout


def normalize_for_match(w):
    """Strip punctuation for matching sense-line words to MorphGNT words."""
    # Normalize all apostrophe variants to one form first
    w = w.replace('\u02bc', "'").replace('\u2019', "'")
    # Remove common punctuation and editorial marks
    return re.sub(r"[.,;·:?!⸀⸁⸂⸃⸄⸅'⁰¹²³⁴⁵⁶⁷⁸⁹\"()\[\]]+", '', w).strip()


def generate_chapter_json(book_file, chapter, stems_db, lexicon, freq,
                          book_code='acts'):
    """Generate the full chapter data array, using sense-lines for layout."""
    words = load_morphgnt_chapter(book_file, chapter)
    sense = load_sense_lines(book_code, chapter)

    if not sense:
        # Fallback: no sense-lines, use simple verse markers
        print("  WARNING: no sense-lines file found, using flat layout",
              file=sys.stderr)
        data = []
        last_verse = 0
        for wd in words:
            v = wd['verse']
            if v != last_verse:
                data.append({'v': v})
                last_verse = v
            data.append(decompose_word(wd, stems_db, lexicon))
        return data

    # Match sense-line words to MorphGNT words
    data = []
    mg_idx = 0  # pointer into morphgnt words

    for item in sense:
        if 'verse' in item:
            data.append({'v': item['verse']})
        elif 'gap' in item:
            # Paragraph gap between verses — skip, verse marker handles it
            pass
        elif 'br' in item:
            data.append({'br': True})
        elif 'word' in item:
            sl_word = item['word']
            sl_clean = normalize_for_match(sl_word)

            if mg_idx >= len(words):
                # Ran out of MorphGNT words — shouldn't happen
                print(f"  WARNING: ran out of MorphGNT words at sense-line word '{sl_word}'",
                      file=sys.stderr)
                continue

            mg_word = words[mg_idx]['word']
            mg_clean = normalize_for_match(mg_word)

            # Normalize apostrophe differences for matching
            sl_norm = sl_clean.replace('\u02bc', "'")
            mg_norm = mg_clean.replace('\u02bc', "'")

            if sl_norm == mg_norm:
                # Match — decompose using MorphGNT data, but use sense-line
                # surface text (preserves editorial punctuation)
                entry = decompose_word(words[mg_idx], stems_db, lexicon)
                # Override the display text with the sense-line version
                # (keeps original punctuation placement)
                entry['txt'] = sl_word
                data.append(entry)
                mg_idx += 1
            else:
                # Try to find match within next few words (minor alignment issue)
                found = False
                for lookahead in range(1, 4):
                    if mg_idx + lookahead < len(words):
                        la_clean = normalize_for_match(
                            words[mg_idx + lookahead]['word']).replace('\u02bc', "'")
                        if sl_norm == la_clean:
                            # Skip unmatched MorphGNT words
                            for skip in range(lookahead):
                                entry = decompose_word(words[mg_idx + skip],
                                                       stems_db, lexicon)
                                data.append(entry)
                            mg_idx += lookahead
                            entry = decompose_word(words[mg_idx], stems_db, lexicon)
                            entry['txt'] = sl_word
                            data.append(entry)
                            mg_idx += 1
                            found = True
                            break
                if not found:
                    print(f"  WARNING: mismatch at idx {mg_idx}: "
                          f"SL='{sl_word}' MG='{mg_word}'", file=sys.stderr)
                    # Use MorphGNT data anyway
                    entry = decompose_word(words[mg_idx], stems_db, lexicon)
                    data.append(entry)
                    mg_idx += 1

    return data


# Bare-gloss overrides applied at lexicon-resolution time. These
# are entries where Dodson's first sense is misleading or obscure;
# we replace it before any inflection logic runs. (Inflection-aware
# per-(lemma, tvm) overrides live separately in inflect_gloss.py.)
_GLOSS_OVERRIDE = {
    'μαθητής': 'disciple',
    'ἀπειλή': 'threat',
    'συναγωγή': 'synagogue',
    'ἐκκλησία': 'church',
    'ἀπόστολος': 'apostle',
    'ἐπιστολή': 'letter',
    'ἀρχιερεύς': 'high priest',
    'παράκλησις': 'encouragement',
    'προσέρχομαι': 'approach',
    'παρίστημι': 'present',
    'σκεῦος': 'vessel',
    'ἐπικαλέω': 'call upon',
    'ἐνώπιον': 'before',
    'ἀποστέλλω': 'send',
    'συνέρχομαι': 'gather',
    'παρακαλέω': 'urge',
    'κατά': 'according to',
    'ἐπί': 'upon',
    'διά': 'through',
    'παρά': 'from',
    'ὑπέρ': 'for',
    'πρός': 'to',
    'ἀφορίζω': 'set apart',  # Dodson "rail off" is obscure
    'συναλίζομαι': 'meet with',  # Dodson "I am assembled together with" → unwieldy
    'χειραγωγός': 'guide',  # Dodson "one who leads a helpless person by the hand" — definitional
    # ── Pre-scale audit additions (lexicon-wide scan, 2026-04-17) ──────────
    # High-frequency semantic/content fixes
    'ἄν': '[modal]',               # Dodson untranslatable 9-word explanation
    'δύναμαι': 'can',              # "am powerful" → NT use = can/be able
    'μέλλω': 'be about to',        # "am about to" — make form full infinitive
    'ἀπέρχομαι': 'depart',         # "come or go away from"
    'ὑπάρχω': 'exist',             # "am" → clashes with εἰμί
    'πάσχω': 'suffer',             # "am acted upon" → NT active meaning
    'δουλεύω': 'serve',            # "am a slave" → NT = actively serve
    'γρηγορέω': 'watch',           # "am awake" → NT idiom
    'εὐδοκέω': 'be pleased',       # "am resolved" is archaic
    'μεριμνάω': 'worry',           # "am anxious"
    'ὑστερέω': 'lack',             # "am lacking"
    'ἐκπλήσσομαι': 'be amazed',    # "am thunderstruck"
    'ζηλόω': 'be zealous',         # "am jealous" too narrow
    'ἄρχω': 'begin',               # "(act.) I reign" — NT overwhelmingly middle "begin"
    'ἅπτω': 'touch',               # "(act.) I kindle" — NT overwhelmingly middle "touch"
    'θεάομαι': 'behold',           # "see" — duplicates ὁράω display
    'πρεσβεύω': 'serve as ambassador',  # "am aged" is wrong for NT use
    'ἀπιστέω': 'disbelieve',       # "am unfaithful"
    'ἀγανακτέω': 'be indignant',   # "am angry"
    'νήφω': 'be sober',            # "am calm" — NT = vigilant
    'λανθάνω': 'escape notice',    # "am hidden"
    'λείπω': 'lack',               # "am wanting" archaic
    'πρόκειμαι': 'lie before',     # "am set before"
    'ἀγρυπνέω': 'keep watch',      # "am awake" → NT = keep watch
    # Long definitional glosses
    'ποτέ': 'once',
    'βάπτισμα': 'baptism',
    'Ἀσία': 'Asia Minor',
    'τράπεζα': 'table',
    'κατεσθίω': 'devour',
    'τάλαντον': 'talent',
    'βῆμα': 'judgment seat',       # Dodson "space covered by a step of the foot" — NT = tribunal
    'ἀντιλέγω': 'contradict',
    'ἀγαθοποιέω': 'do good',
    'δικαίωμα': 'righteous act',
    'παῖς': 'child',
    'βλασφημία': 'blasphemy',
    'δράκων': 'dragon',
    'Ἕλλην': 'Greek',              # "Hellene" — standard English = Greek
    'Ἰούδας': 'Judas',             # "Judah" — NT person = Judas
    'Μαριάμ': 'Mary',              # "Miriam" — NT form = Mary
    'ἀδόκιμος': 'disqualified',
    'βοηθέω': 'help',
    'πραιτώριον': 'praetorium',
    'ἀξιόω': 'consider worthy',
    'Ἑβραϊστί': 'in Hebrew',
    'βάρβαρος': 'foreigner',
    'χειροποίητος': 'hand-made',
    'ἀναπέμπω': 'send back',
    'μεθίστημι': 'transfer',
    'πρωτοκλισία': 'place of honor',
    'σκηνόω': 'dwell',
    'ἐκτίθημι': 'explain',         # "put out or expose a child" — NT = expound
    'γονυπετέω': 'kneel before',
    'εἰδωλολατρία': 'idolatry',
    'ἀποδεκατόω': 'tithe',
    'ἀποβαίνω': 'disembark',
    'περιπίπτω': 'fall among',
    'βουλευτής': 'council member',
    'πολιτεύομαι': 'live as a citizen',
    'παραθήκη': 'deposit',
    'παρεπίδημος': 'sojourner',
    'ἱεράτευμα': 'priesthood',
    'ἀλλοτριεπίσκοπος': 'meddler',
    'ὀφθαλμοδουλία': 'eye-service',
    'ἀμήτωρ': 'without mother',
    'νεφρός': 'inner being',       # Dodson "kidney as a general emotional center"
    'αἱματεκχυσία': 'shedding of blood',
    'Ἀρεοπαγίτης': 'Areopagite',
    'βασκαίνω': 'bewitch',
    'σιτομέτριον': 'food ration',
    'ἐσχάτως': "at death's door",
    'σάλος': 'rough sea',
    'σπένδομαι': 'be poured out',
    'νομοδιδάσκαλος': 'teacher of the law',
    # Punctuation-laden interjections
    'ἰδού': 'behold!',
    'ἴδε': 'look!',
    'ὄφελον': 'would that',
    # ── Pre-scale non-Acts trap lemmas (freq ≥10, not in Acts) ─────────
    # Surfaced by lexicon scan 2026-04-17; all have Dodson glosses that
    # produce awkward or incorrect output when inflected.
    'ἀμήν':          'amen',                # 128x; Dodson runs 4 synonyms
    'δοκιμάζω':      'test',                # long multi-sense
    'γεωργός':       'farmer',              # definitional
    'οἰκοδομή':      'building',            # long
    'ῥίζα':          'root',                # self-referential
    'δεῖπνον':       'dinner',              # long
    'σφραγίς':       'seal',                # long
    'ποτίζω':        'give to drink',
    'συνίστημι':     'commend',             # 5 senses in Dodson
    'ἀνά':           'up',                  # overstuffed preposition entry
    'δαιμονίζομαι':  'be demon-possessed',
    'καταισχύνω':    'shame',
    'ἀναπαύω':       'give rest',
    'ἀναπίπτω':      'recline',
    'ὑγιαίνω':       'be healthy',
    'γέμω':          'be full of',
    'ἐπαισχύνομαι':  'be ashamed',
    'ἀναφέρω':       'offer up',
    'μακροθυμέω':    'be patient',
    'δικαιόω':       'justify',             # Dodson "make righteous" — NT standard is "justify"
    'ἀληθής':        'true',                # Dodson "unconcealed" is etymological; NT use = "true"
    'ἀληθινός':      'true',                # same etymological issue
    'ἀλήθεια':       'truth',               # confirm clean default
    # ── Chapter-reviewer findings (Acts 13, 17, 26, Romans 3) ─────────────
    'κατοικέω':      'live in',             # "dwell in" — archaic
    'ἅγιος':         'holy',                # "set apart" — etymological; "holy" standard
    'ἐγκαλέω':       'accuse',              # passive rendered "is brought a charge against"
    'ἀχρειόομαι':    'be useless',          # "be good for nothing"
    'σύντροφος':     'childhood companion', # "foster brother" — archaic
    # ── Sonnet etymological-sweep adds (NT-standard over Dodson first-senses) ──
    'γίνομαι':       'become',              # Dodson "come into being" → NT primary
    'οὐρανός':       'heaven',              # "the sky" → heaven (theological)
    'δόξα':          'glory',               # "honor" → NT standard = glory
    'βασιλεία':      'kingdom',             # "kingship" → NT noun = kingdom
    'ἔθνος':         'nation',              # "a race" → nation/Gentiles
    'φωνή':          'voice',               # "a sound" → voice
    'ψυχή':          'soul',                # "the soul, life, self"
    'ἀποθνῄσκω':     'die',                 # "I am dying, am about to die"
    'σῴζω':          'save',                # "I save, heal"
    'ζητέω':         'seek',
    'ἀκολουθέω':     'follow',              # "I accompany, attend, follow"
    'ἀφίημι':        'forgive',             # "I send away" → NT primary = forgive/leave
    'ἐγείρω':        'raise',               # "I wake, arouse" → NT = raise (resurrection)
    'αἴρω':          'take up',             # "I raise, lift up"
    'φυλακή':        'prison',              # "a watching"
    'ῥῆμα':          'word',                # "a thing spoken"
    'σωτηρία':       'salvation',           # "deliverance"
    'πληρόω':        'fulfill',             # "I fill, fulfill"
    'ἐκβάλλω':       'cast out',            # "I throw"
    'βαπτίζω':       'baptize',             # "I dip, submerge" — "dip" misleads
    'σημεῖον':       'sign',                # "a sign, miracle"
    'μαρτυρέω':      'testify',             # "I witness"
    'εὐαγγέλιον':    'gospel',              # "the good news"
    'ἀποκτείνω':     'kill',                # "I put to death, kill"
    'τηρέω':         'keep',                # "I keep, guard, observe"
    'τιμή':          'honor',               # "a price, honor" — price rare in NT
    'περισσεύω':     'abound',              # "I exceed, am left over"
    'κρίσις':        'judgment',            # "judging" (gerund) → NT noun
    'θλῖψις':        'tribulation',         # "persecution"
    'θαυμάζω':       'marvel',              # "I wonder, admire"
    'φωνέω':         'call',                # "I crow, shout, summon" — "crow" is of roosters
    'ἐγγίζω':        'draw near',           # "I come near, approach"
    'ἐργάζομαι':     'work',                # Dodson has typo "I word, trade, do"
    'ὑποτάσσω':      'submit',              # "I place under, subject to"
    'διακονέω':      'serve',               # "I wait at table, serve"
    'διακονία':      'ministry',            # "waiting at table, service"
    'ἐπιστρέφω':     'turn',                # "I turn back to"
    'Σατανᾶς':       'Satan',               # "an adversary, Satan" — proper name
    'διάβολος':      'devil',               # "slanderous, the Slanderer"
    'ἀρχή':          'beginning',           # "ruler, beginning" — ἄρχων = ruler
    'λογίζομαι':     'reckon',              # Pauline standard
    'καταργέω':      'abolish',             # "I bring to naught, sever"
    'μυστήριον':     'mystery',             # "anything hidden"
    'διαθήκη':       'covenant',            # "a covenant, will, testament"
    'ἐνδύω':         'clothe',              # "I put on, clothe"
    'θυμός':         'wrath',               # "an outburst of passion"
    'ὁμολογέω':      'confess',
    'ἄφεσις':        'forgiveness',         # "deliverance, pardon"
    'ἀποκαλύπτω':    'reveal',
    'ἀποκάλυψις':    'revelation',          # "an unveiling, uncovering"
    'χαρίζομαι':     'forgive',             # "I show favor to, forgive"
    'χάρισμα':       'gift',                # "an undeserved favor"
    'εὐλογία':       'blessing',            # "adulation, praise, blessing" — "adulation" wrong
    'ἐκπορεύομαι':   'go out',              # "I journey out, come forth"
    'ὑπομένω':       'endure',              # "I remain behind, endure"
    'φαίνω':         'appear',              # "I shine, appear, seem" — NT primary = appear
    'λυπέω':         'grieve',
    'κοιμάομαι':     'sleep',               # "I fall asleep" — euphemism for die
    'ἀθετέω':        'reject',              # "I annul"
    'πειρασμός':     'temptation',          # "trial, testing, temptation"
    'στρέφω':        'turn',
    'ὑψόω':          'exalt',
    'φανερόω':       'reveal',
    'θεμέλιος':      'foundation',
    'κοπιάω':        'labor',               # "I grow weary, toil"
    'σκάνδαλον':     'stumbling block',
    'εἰκών':         'image',
    'ἀρέσκω':        'please',
    'διακρίνω':      'doubt',               # "I distinguish, discern, doubt" — NT James/Romans = doubt
    'δέσμιος':       'prisoner',            # "one bound, a prisoner"
    'δεσμός':        'chain',               # "a bond, chain"
    'ξένος':         'stranger',            # "new, novel, a foreigner"
    'γυμνός':        'naked',               # "wearing only the under-garment"
    'συμφέρω':       'be profitable',       # "I collect, am profitable to"
    'κολλάομαι':     'cling to',            # "I glue, cleave"
    'συνέχω':        'compel',              # "I press together, confine, compel"
    'πρόθεσις':      'purpose',             # "the show-bread, predetermination" — Pauline = purpose
    'ἀναχωρέω':      'withdraw',            # "I return, retire, depart, withdraw" — "I return" is wrong first sense
    'ὑστέρημα':      'need',                # "that which is lacking, poverty"
    'ἄφρων':         'fool',                # "senseless, foolish"
    'ἰσχύω':         'be able',             # "I am strong, able" — NT primary
    'πάρειμι':       'be present',
    'μεθύω':         'be drunk',
    'καθέζομαι':     'sit',
    'ἀρκέω':         'be content',          # "I am sufficient, I suffice"
    'θαρρέω':        'be confident',        # "I am courageous"
    'σωφρονέω':      'be self-controlled',  # "I am sober-minded"
    'ἀπορέω':        'be perplexed',        # "I am in difficulties"
    'αἰσχύνομαι':    'be ashamed',
    'ἐκλύομαι':      'grow weary',          # "I am unstrung" — archaic
    'μαίνομαι':      'be mad',              # "I am raving mad"
    # ── Reviewer batch 2 overrides (post-Bundle-3 horde) ─────────────────
    'εἰμί':          'be',                  # CRITICAL: bare "am" caused "was amming" bug
    'Χριστός':       'Christ',              # proper name, not etymological "anointed"
    'κύριος':        'Lord',                # capitalized (NT-theological standard)
    'ἀνήρ':          'man',                 # "male human being" too clinical
    'αἵρεσις':       'sect',                # "self-chosen opinion" definitional
    'μέν':           'indeed',              # "truly" archaic for this particle
    'ὅθεν':          'therefore',           # "whence" archaic
    'ὑποβάλλω':      'instigate',           # "suborn" archaic legal English
    'ἐκλογή':        'election',            # "choosing out" — theological standard
    'ἐνδείκνυμαι':   'demonstrate',         # "show forth" archaic
    'εὐρακύλων':     'northeaster',         # drop the parenthetical "(wind)"
    'συντρίβω':      'crush',               # "break by crushing" redundant
    'δίδωμι':        'give',                # "offer" etymological drift
    'βούλομαι':      'want',                # "will" leads Dodson entry, confusing
    'ἐπέχω':         'fix attention on',    # "hold forth" archaic
    'μεταμορφόομαι': 'be transformed',      # "change the form" awkward
    'μετοικίζω':     'resettle',            # "transport" stiff
    'ἐμφανίζω':      'reveal',              # "make visible" wordy
    'ἀδικέω':        'wrong',               # "act unjustly towards" wordy
    'ἀνατίθεμαι':    'lay before',          # "lay a case before" wordy
    'εἰσπηδάω':      'rush in',             # "leap into" stiff
    'παρανομέω':     'break the law',       # "act contrary to law"
    'προσκλίνομαι':  'adhere to',
    'ἀναστρέφω':     'conduct oneself',
    'πράσσω':        'do',                  # confirm — standard
    'ἀνθίστημι':     'withstand',           # "take a stand against" wordy
    # ── Horde batch 3 (post-parse-order-fix reviewer horde) ────────────
    # The π pattern: "wind" for πνεῦμα was flagged by 5+ independent
    # reviewers (Eph 6, 2 Thess 2, Jude 19, Gal 5). Highest-value fix.
    'πνεῦμα':        'spirit',              # "wind" → NT = Spirit / spirit
    'εὐαγγελίζω':    'announce the gospel', # "bring good news" is definitional
    'ἀρχάγγελος':    'archangel',           # "ruler of angels" — etymological
    'ἔσωθεν':        'within',              # "from within" — etymological
    'ὄπισθεν':       'behind',              # "from behind" — etymological
    'ξενίζω':        'surprise',            # "entertain a stranger" — wrong primary sense in 1 Peter
    'πρωτότοκος':    'firstborn',           # "first-born" is fine but override for standard NT form
    # Gal 5:22-23 fruit of the Spirit — standardize to modern English NT
    'χρηστότης':     'kindness',
    'ἀγαθωσύνη':     'goodness',
    'πραΰτης':       'gentleness',          # was "mildness" — KJV/NRSV standard
    'ἐγκράτεια':     'self-control',        # was "self-mastery"
    # Other flagged by horde
    'παρρησία':      'boldness',            # "freedom" incomplete
    'λοιπός':        'remaining',           # "left" etymological
    'ἐργάτης':       'worker',              # "field-laborer" too specific
    'ὀκνηρός':       'lazy',                # "slothful" archaic
    'δαιμονιώδης':   'demonic',             # "demon-like" morpheme-y
    'σπλαγχνίζομαι': 'have compassion',     # "have pity" awkward in NT
    'ὀργίζομαι':     'be angry',            # "irritated" too mild
    'διαγογγύζω':    'grumble',             # "murmur greatly" archaic
    'καταφιλέω':     'kiss',                # "kiss affectionately" redundant
    'ὑπερυψόω':      'exalt',               # "highly exalt" → "highlied" engine bug fix
    'προδίδωμι':     'betray',              # "give before" semantically wrong for NT
    'φωσφόρος':      'morning star',        # "light-bearing" etymological
    'ἐκκεντέω':      'pierce',              # "pierce through" redundant
    'μεριμνάω':      'worry',               # confirm (may already be set)
    'ἐπιχειρέω':     'attempt',             # "take in hand" archaic
    'αὐτόπτης':      'eyewitness',          # "eye-witness" etymological hyphenation
    'κράτιστος':     'most excellent',      # retain — context-acceptable (formal address)
    'κατηχέω':       'teach',               # "instruct orally" definitional
    'ἵνα':           'so that',             # "in order that" formal/archaic
    'ἐπιγινώσκω':    'recognize',           # "come to know" wordy
    'θάλασσα':       'sea',                 # confirm
    'μεθίστημι':     'remove',              # "move out of place" wordy (already in table; confirming)
    'ἀμεταμέλητος':  'irrevocable',         # confirm
    'ὑποστέλλω':     'shrink back',         # reviewer context
    'πληροφορέω':    'assure',              # "carry out fully" etymological
    'γνωρίζω':       'make known',          # confirm natural gloss
    'ἐπεγείρω':      'stir up',             # confirm
    'νεομηνία':      'new moon',            # confirm
    'πυρόομαι':      'be set ablaze',       # reviewer-noted cleaner rendering
    'ὀφείλημα':      'debt',                # confirm
    'κατακολουθέω':  'follow after',        # confirm
    'φθάνω':         'arrive',              # "anticipate" semantically wrong (means temporal precedence)
    'ἡγέομαι':       'consider',            # "lead" is secondary NT sense
    'ἐλπίζω':        'hope',                # confirm
}


def resolve_bare_gloss(lemma, lexicon):
    """Resolve a lemma to its bare display gloss (post-override,
    post-strip). Returns '' if no gloss is available.

    This is the single source of truth used by BOTH the lex-table
    builder and the per-word inflection step, so both stay in sync.
    """
    if lemma in _GLOSS_OVERRIDE:
        return _GLOSS_OVERRIDE[lemma]
    entry = lexicon.get(lemma, {})
    gl = entry.get('gloss', '')
    if not gl:
        return ''
    if isinstance(gl, list):
        gl = gl[0] if gl else ''
    if not isinstance(gl, str):
        gl = str(gl)
    short = gl.split(',')[0].strip()
    # Strip leading Dodson voice/usage annotation: "(act.) I reign" → "I reign"
    short = re.sub(r'^\([^)]*\)\s*', '', short)
    for prefix in ('I ', 'a ', 'an ', 'the '):
        if short.startswith(prefix):
            short = short[len(prefix):]
            break
    # Pipeline rule: Dodson disjunctive first-segments like
    # "come or go away from" → take the head verb only ("come") so
    # inflection doesn't produce "came or go away from". Applies to
    # " or " and " and "; splits and keeps the left side's structure
    # but strips the disjunction + right branch.
    for conj in (' or ', ' and '):
        if conj in short:
            left = short.split(conj)[0].strip()
            # After the split, keep the right-branch tail ("away from")
            # if it's clearly a preposition phrase and not a second verb.
            # Heuristic: if what follows after conj+word is a preposition
            # ("from", "to", "at", "in", "out"), append it.
            right = short[len(left) + len(conj):].strip()
            m = re.match(r'^\S+\s+(from|to|at|in|out|off|up|down|against|with|on|about|into|upon|over|under)(\b.*)?$', right)
            if m:
                short = f'{left} {m.group(1)}{m.group(2) or ""}'.strip()
            else:
                short = left
            break
    # Pipeline rule: Dodson often gives multi-exclamation synonym lists
    # like "See! Lo! Behold! Look!". Keep only the first exclamation.
    if short.count('!') >= 2:
        m = re.match(r'^[^!]*!', short)
        if m:
            short = m.group(0).strip()
    # Pipeline rule: stripped "I am X" form ("am strong", "am weak")
    # reads like a parsing note, not a gloss. Convert to bare infinitive
    # "be X". Does NOT apply to εἰμί itself (handled via override) or
    # to "am about to" etc. (which have per-lemma overrides).
    if short.startswith('am ') and not short.startswith('am about'):
        short = 'be ' + short[3:]
    # Strip trailing single "?" or "!" punctuation (e.g. "why?", "woe!")
    # when the whole gloss is a single word with trailing punct.
    if re.fullmatch(r'[a-zA-Z]+[?!]', short):
        short = short[:-1]
    return short


def generate_lexicon_json(words, lexicon, freq):
    """Generate the LEX object for glosses."""
    lex = {}
    seen = set()
    for wd in words:
        lemma = wd['lemma']
        if lemma in seen:
            continue
        seen.add(lemma)
        short = resolve_bare_gloss(lemma, lexicon)
        if short:
            lex[lemma] = {'gl': short, 'f': freq.get(lemma, 0)}
    return lex


def build_chapter(book_code, chapter, stems_db, lexicon, freq):
    """Build the full per-chapter output dict, using pre-loaded databases.

    This is the reusable in-process entry point — callers load
    stems/lexicon/freq ONCE and reuse across many chapters to avoid
    ~4s of redundant YAML parsing per chapter.
    """
    if book_code not in BOOKS:
        raise ValueError(f'unknown book code: {book_code!r}')
    book_display = BOOKS[book_code]['display']
    morphgnt_file = morphgnt_path_for(book_code)
    words = load_morphgnt_chapter(morphgnt_file, chapter)
    data = generate_chapter_json(morphgnt_file, chapter, stems_db, lexicon, freq,
                                 book_code=book_code)
    lex = generate_lexicon_json(words, lexicon, freq)
    return {
        'book': book_display,
        'chapter': chapter,
        'data': data,
        'lex': lex,
    }


def main():
    # Backwards-compat: `python generate_chapter.py 9` still works for Acts.
    # New form: `python generate_chapter.py --book romans 3`.
    import argparse
    parser = argparse.ArgumentParser(description='Generate per-chapter morph JSON.')
    parser.add_argument('chapter', type=int, help='Chapter number within the book')
    parser.add_argument('--book', default='acts',
                        help='Book code from src/books.py (default: acts)')
    args = parser.parse_args()

    book_code = args.book.lower()
    chapter = args.chapter
    if book_code not in BOOKS:
        print(f'ERROR: unknown book code {book_code!r}. Known: '
              f'{", ".join(sorted(BOOKS.keys()))}', file=sys.stderr)
        sys.exit(2)
    book_display = BOOKS[book_code]['display']

    print(f"Loading stems...", file=sys.stderr)
    stems_db = load_stems()
    print(f"  {len(stems_db)} verb entries", file=sys.stderr)

    print(f"Loading lexicon...", file=sys.stderr)
    lexicon = load_lexicon()
    print(f"  {len(lexicon)} entries", file=sys.stderr)

    print(f"Loading frequencies...", file=sys.stderr)
    freq = load_nt_frequencies()
    print(f"  {len(freq)} lemmas", file=sys.stderr)

    print(f"Processing {book_display} {chapter}...", file=sys.stderr)
    output = build_chapter(book_code, chapter, stems_db, lexicon, freq)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Done: {len(output['data'])} entries", file=sys.stderr)


if __name__ == '__main__':
    main()
