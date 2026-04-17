#!/usr/bin/env python3
"""
morpheus.py — Koine Greek morpheme decomposition engine.

Pipeline architecture: each function handles one decomposition layer.
  1. resolve_stems()   → look up stem data for the lemma/tense
  2. split_prefix()    → identify preposition prefix on compound verbs
  3. split_augment()   → identify augment (syllabic, temporal, compound-internal)
  4. split_formative() → identify tense formative (σ, κ, θ, ψ, ξ, θη, etc.)
  5. split_ending()    → whatever remains is the personal ending or case suffix
  6. split_nominal()   → case suffix extraction for nouns/adj/pronouns

All functions operate on plain strings and return plain strings.
No side effects, no mutation, easy to test.
"""
import re
import unicodedata


# ═══════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════

def strip_accents(s):
    """Remove all combining marks (accents, breathings) for comparison."""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def na(s):
    """Shorthand: normalize for accent-insensitive, case-insensitive compare."""
    return strip_accents(s).lower() if s else ''


def clean_stem_val(s):
    """Clean a stem value from the DB: strip {tags}, pipe |, take first / variant."""
    if not s:
        return ''
    s = re.sub(r'\{[^}]*\}', '', s)
    s = s.replace('|', '')
    if '/' in s:
        s = s.split('/')[0]
    return s.strip()


def clean_surface(text):
    """Clean surface text: strip editorial marks and trailing punctuation."""
    s = re.sub(r'[⸀⸁⸂⸃⸄⸅⁰¹²³⁴⁵⁶⁷⁸⁹]', '', text)
    return s.strip('.,;·:?!')


# ═══════════════════════════════════════════
# CHANNEL-AWARE SEGMENTATION
# ═══════════════════════════════════════════
# Greek morphology has overlapping morphemes. Example: νηστεύσαντες
#   σα  = aorist formative (teal background zone)
#   σαντες = participle ending (underline zone)
#   ες   = case suffix (case-color zone)
# The α is simultaneously end-of-formative AND start-of-participle-marker.
# We represent this via multiple "channels" each with their own independent
# span list; then compute atomic segments via the union of all boundaries.

def build_channels(form, pieces, cs):
    """Build channel-aware span data from decomposed pieces.

    pieces: dict with keys pfx, aug, rdp, stm, frm, pmk, suf (strings, may be '')
            pmk = "participle morpheme kernel" — the middle portion of a
            participle ending that isn't the formative or case suffix
    cs: case code ('n','g','d','a','v') or None
    Returns dict of channel_name -> list of (start, end, role) tuples.
    """
    channels = {'morph': [], 'ptc': [], 'case': []}

    # Walk pieces left-to-right, building morph channel
    i = 0
    for key in ('pfx', 'aug', 'rdp', 'stm', 'frm', 'pmk', 've', 'suf'):
        val = pieces.get(key, '') or ''
        if val:
            end = i + len(val)
            channels['morph'].append((i, end, key))
            i = end

    # Participle overlay: if pmk exists, the participle marker spans
    # from the start of frm (if any) through the end of the word.
    # This is the "underline zone" the user described.
    if pieces.get('pmk'):
        # Find start of ptc marker zone = start of frm (if present), else start of pmk
        ptc_start = None
        ptc_end = len(form)
        pos = 0
        for key in ('pfx', 'aug', 'rdp', 'stm', 'frm', 'pmk', 'suf'):
            val = pieces.get(key, '') or ''
            if key == 'frm' and val:
                ptc_start = pos
            elif key == 'pmk' and val and ptc_start is None:
                ptc_start = pos
            pos += len(val)
        if ptc_start is not None:
            channels['ptc'].append((ptc_start, ptc_end, 'marker'))

    # Case overlay: case color lives on the suffix (not on verb endings)
    if pieces.get('suf') and cs:
        suf_len = len(pieces['suf'])
        channels['case'].append((len(form) - suf_len, len(form), cs))

    return channels


def segment_channels(form, channels):
    """Compute atomic segments via the union of all channel boundaries.
    Each segment carries a dict of {channel_name: role}.
    Returns a list of {'t': text, 'ch': {channel: role}}.
    """
    if not form:
        return []

    breaks = {0, len(form)}
    for spans in channels.values():
        for start, end, _ in spans:
            breaks.add(start)
            breaks.add(end)

    cuts = sorted(breaks)
    segs = []
    for a, b in zip(cuts, cuts[1:]):
        if a >= b:
            continue
        ch_at = {}
        for ch_name, spans in channels.items():
            for start, end, role in spans:
                if start <= a and b <= end:
                    ch_at[ch_name] = role
                    break
        segs.append({'t': form[a:b], 'ch': ch_at})
    return segs


# ═══════════════════════════════════════════
# PREPOSITION PREFIXES
# ═══════════════════════════════════════════

# Sorted longest-first for greedy matching.
# Each entry: (surface form that might appear, canonical preposition)
PREFIXES = sorted([
    ('προσ', 'προσ'), ('ἀνταν', 'ἀντι'), ('ἀντι', 'ἀντι'), ('ἀντ', 'ἀντι'), ('ἀνθ', 'ἀντι'),
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
], key=lambda x: -len(x[0]))


# ═══════════════════════════════════════════
# TEMPORAL AUGMENT PATTERNS
# ═══════════════════════════════════════════
# (augmented_vowel_stripped, unaugmented_vowel_stripped, aug_char_len, unaug_char_len)
TEMPORAL_AUGMENTS = [
    ('ηυ', 'ευ', 2, 2),
    ('ηυ', 'αυ', 2, 2),
    ('ῃ',  'αι', 1, 2),
    ('ῳ',  'οι', 1, 2),
    ('ει', 'ι',  2, 1),
    ('ει', 'ε',  2, 1),   # rare but exists (ε→ει)
    ('η',  'α',  1, 1),
    ('η',  'ε',  1, 1),
    ('ω',  'ο',  1, 1),
]

# Suppletive verbs where the aorist stem is unrelated to the present,
# and the augment is baked into the stem form in a way the DB can't distinguish.
SUPPLETIVE_AUGMENTS = {
    'λέγω':      {('A','A'): 'εἶ', ('A','M'): 'εἶ'},
    'ὁράω':      {('A','A'): 'εἶ'},
    'φέρω':      {('A','A'): 'ἤ'},
    'αἱρέω':     {('A','A'): 'εἷ'},
    'ἐσθίω':     {('A','A'): 'ἔ'},
    'πίνω':      {('A','A'): 'ἔ'},
    'ἔρχομαι':   {('A','A'): 'ἦ', ('A','M'): 'ἦ'},
    'ἔχω':       {('I','A'): 'εἶ'},
    'ἐργάζομαι': {('A','M'): 'ἠ', ('A','P'): 'ἠ'},
}


# ═══════════════════════════════════════════
# STEP 1: RESOLVE STEMS
# ═══════════════════════════════════════════

# Principal part key mapping: (tense, voice) → stem key
STEM_KEY_MAP = {
    ('P', 'A'): '1-', ('P', 'M'): '1-', ('P', 'P'): '1-',
    ('I', 'A'): '1+', ('I', 'M'): '1+', ('I', 'P'): '1+',
    ('F', 'A'): '2-', ('F', 'M'): '2-',
    ('A', 'A'): '3-', ('A', 'M'): '3-',
    ('X', 'A'): '4-', ('Y', 'A'): '4+',
    ('X', 'M'): '5-', ('X', 'P'): '5-',
    ('Y', 'M'): '5+', ('Y', 'P'): '5+',
    ('A', 'P'): '6-', ('F', 'P'): '7-',
}

AUG_KEY_MAP = {
    ('I', 'A'): ('1+', '1-'), ('I', 'M'): ('1+', '1-'), ('I', 'P'): ('1+', '1-'),
    ('A', 'A'): ('3+', '3-'), ('A', 'M'): ('3+', '3-'),
    ('Y', 'A'): ('4+', '4-'),
    ('Y', 'M'): ('5+', '5-'), ('Y', 'P'): ('5+', '5-'),
    ('A', 'P'): ('6+', '6-'),
}


def resolve_stems(stems_dict, tense, voice):
    """Look up the relevant stems for this tense/voice combination.
    Returns (stem_val, aug_stem, unaug_stem, present_stem).
    All values are cleaned strings.
    """
    key = STEM_KEY_MAP.get((tense, voice))
    stem_val = clean_stem_val(stems_dict.get(key, '')) if key else ''

    # Fallback: if unaugmented not available, try augmented
    if not stem_val and key and key.endswith('-'):
        stem_val = clean_stem_val(stems_dict.get(key[:-1] + '+', ''))

    # Augmented/unaugmented pair for augment detection
    aug_keys = AUG_KEY_MAP.get((tense, voice))
    aug_stem = clean_stem_val(stems_dict.get(aug_keys[0], '')) if aug_keys else ''
    unaug_stem = clean_stem_val(stems_dict.get(aug_keys[1], '')) if aug_keys else ''

    # Present stem (PP1) for formative comparison
    present_stem = clean_stem_val(stems_dict.get('1-', ''))

    return stem_val, aug_stem, unaug_stem, present_stem


# ═══════════════════════════════════════════
# STEP 2: SPLIT PREFIX
# ═══════════════════════════════════════════

def split_prefix(form, stem_val, present_stem='', lemma=''):
    """Identify a preposition prefix on a compound verb.
    Returns (prefix, remainder) where prefix may be ''.

    Strategy: check if the lemma starts with a known preposition prefix
    OR any phonological variant of it. The form may use a different surface
    variant of the same prefix (e.g. συγχέω → συνέχυννεν, ν assimilation).
    """
    if not form:
        return '', form

    form_na = na(form)
    lemma_na = na(lemma) if lemma else ''

    # Build canonical → variants map for assimilation-aware matching
    canonicals = {}
    for pf, canon in PREFIXES:
        canonicals.setdefault(canon, []).append(pf)

    # Find lemma's prefix (what canonical prefix does the lemma start with?)
    lemma_canonical = None
    lemma_pf_len = 0
    for pf, canon in PREFIXES:
        pf_na = na(pf)
        if lemma_na.startswith(pf_na) and len(pf_na) > lemma_pf_len:
            lemma_canonical = canon
            lemma_pf_len = len(pf_na)

    # If lemma has a prefix, allow form to use ANY variant of the same canonical
    # Also: if the lemma has multiple stacked prefixes (e.g. ἐξαποστέλλω = ἐξ+ἀπό+στέλλω),
    # strip them all in one pass.
    if lemma_canonical:
        total_pfx_form = ''
        current_form_na = form_na
        current_form = form
        current_lemma_na = lemma_na
        current_lemma = lemma
        while True:
            # Find canonical at current lemma start
            canon = None
            canon_pf_len = 0
            for pf, c in PREFIXES:
                pf_na = na(pf)
                if current_lemma_na.startswith(pf_na) and len(pf_na) > canon_pf_len:
                    canon = c
                    canon_pf_len = len(pf_na)
            if not canon:
                break
            # Try matching any variant of this canonical against the form
            matched = None
            for variant in sorted(canonicals[canon], key=len, reverse=True):
                v_na = na(variant)
                if current_form_na.startswith(v_na):
                    matched = variant
                    break
            if not matched:
                break
            # Accumulate the prefix
            total_pfx_form += current_form[:len(matched)]
            current_form = current_form[len(matched):]
            current_form_na = na(current_form)
            current_lemma = current_lemma[canon_pf_len:]
            current_lemma_na = na(current_lemma)
        if total_pfx_form:
            return total_pfx_form, form[len(total_pfx_form):]

    # Fallback: direct matching (same variant in form and lemma)
    for pf, canonical in PREFIXES:
        pf_na = na(pf)
        if form_na.startswith(pf_na) and lemma_na.startswith(pf_na):
            # Both form and lemma start with this prefix → compound verb
            # Use the actual characters from the form for display
            return form[:len(pf)], form[len(pf):]

    return '', form


# ═══════════════════════════════════════════
# STEP 3: SPLIT AUGMENT
# ═══════════════════════════════════════════

def split_augment(form, prefix, aug_stem, unaug_stem, lemma, tense, voice, mood):
    """Identify the augment in a verb form.
    Only applies to indicative mood (aorist, imperfect, pluperfect).

    Returns (augment, remainder) where augment may be ''.
    `form` should already have the prefix stripped.
    """
    # Augment only in indicative
    if mood != 'I':
        return '', form

    # Only past tenses have augments
    if tense not in ('A', 'I', 'Y'):
        return '', form

    aug = ''
    aug_from_db = _detect_augment_from_stems(aug_stem, unaug_stem, prefix)

    if aug_from_db:
        aug = aug_from_db
    else:
        # Suppletive fallback
        sup = SUPPLETIVE_AUGMENTS.get(lemma, {})
        aug = sup.get((tense, voice), '')

    if not aug:
        # Surface-based fallback: when DB has no aug/unaug pair to compare,
        # detect the augment directly from the form (post-prefix-strip).
        # form here is already the remainder after prefix stripping.
        aug = _detect_augment_from_surface(form, lemma, prefix)

    if not aug:
        return '', form

    # Find the augment in the actual form text (accent/case insensitive)
    aug_na = na(aug)
    form_na = na(form)

    if form_na.startswith(aug_na):
        actual_aug = form[:len(aug)]
        remainder = form[len(aug):]
        return actual_aug, remainder

    # Augment detected but doesn't match the form start — discard
    return '', form


def _detect_augment_from_surface(remainder, lemma, prefix):
    """Fallback augment detection from the surface form when DB stems
    can't distinguish aug/unaug. Used for compound verbs where only the
    augmented form (3+) is in the DB.

    `remainder` is the form with the prefix already stripped.
    Returns the augment string or ''.
    """
    if not remainder:
        return ''

    # Determine the expected "unaugmented start" = the lemma with prefix stripped.
    # This gives us what the form would look like without an augment.
    lemma_stripped = lemma
    if prefix and lemma:
        pfx_na = na(prefix)
        lem_na = na(lemma)
        if lem_na.startswith(pfx_na):
            lemma_stripped = lemma[len(prefix):]

    if not lemma_stripped:
        return ''

    rem_na = na(remainder)
    lem_na = na(lemma_stripped)

    # Case 1: syllabic augment ε- prepended to a consonant-initial stem
    # e.g. lemma στέλλω → ἔστειλα; post-prefix stripping of ἀποστέλλω: ἔστειλαν
    if rem_na.startswith('ε') and lem_na and lem_na[0] not in 'αεηιουωῃῳ':
        # Verify: rem[1:] should begin with the same consonant as lemma
        if len(rem_na) > 1 and rem_na[1] == lem_na[0]:
            return remainder[0]

    # Case 2: syllabic augment where prefix's final vowel dropped
    # e.g. ἀποπίπτω → ἀπέπεσαν. Post strip ἀπ: 'έπεσαν'. Lemma stripped of ἀπ:
    # 'οπίπτω'. rem starts with ε, lemma-stripped starts with ο (dropped vowel).
    if rem_na.startswith('ε') and lem_na and lem_na[0] in 'οαι':
        # Verify: after the ε, the rest matches lemma's 2nd char onward
        if len(rem_na) > 1 and len(lem_na) > 1 and rem_na[1] == lem_na[1]:
            return remainder[0]

    # Case 3: temporal augment (vowel lengthening at start of stem)
    TEMPORAL_PATTERNS = [
        ('η', 'α'), ('η', 'ε'), ('ω', 'ο'),
        ('ηυ', 'ευ'), ('ηυ', 'αυ'),
        ('ει', 'ι'), ('ει', 'ε'),
    ]
    for aug_pat, unaug_pat in TEMPORAL_PATTERNS:
        if rem_na.startswith(aug_pat) and lem_na.startswith(unaug_pat):
            # Verify: after the augmented vowel, rest matches lemma's next chars
            rem_after = rem_na[len(aug_pat):]
            lem_after = lem_na[len(unaug_pat):]
            # Allow partial match (stem may have changed for aorist)
            if len(rem_after) > 0 and len(lem_after) > 0 and rem_after[:1] == lem_after[:1]:
                return remainder[:len(aug_pat)]

    # Case 4: temporal augment with compound prefix vowel elision
    # e.g. κατακληρονόμησεν: prefix κατα → κατ, then ε is augment before κληρ.
    # rem_na starts with 'ε' and lem_na starts with 'α' (the elided prefix-end vowel)
    # or some other short vowel. If the next chars match after the ε/α skip:
    if rem_na.startswith('ε') and lem_na and lem_na[0] in 'αο':
        rem_rest = rem_na[1:]
        lem_rest = lem_na[1:]
        if rem_rest.startswith(lem_rest[:2]) or (lem_rest and rem_rest.startswith(lem_rest[0])):
            return remainder[0]

    # Case 5: temporal augment ι → η (e.g. καθίημι → καθῆκα)
    # The stem may differ in aorist forms (root aorist), so don't require
    # exact match beyond the augmented vowel itself.
    if rem_na.startswith('η') and lem_na.startswith('ι'):
        return remainder[0]

    # Case 6: loose rule for compound verbs with ν-drop or other
    # assimilation where the lemma form doesn't cleanly match.
    # If we have a prefix AND the remainder starts with ε (syllabic augment),
    # accept it. Most false positives here are themselves legitimate: an ε
    # appearing right after a preposition prefix in a past-tense verb almost
    # always IS the augment.
    if prefix and rem_na.startswith('ε'):
        return remainder[0]

    return ''


def _strip_prefix_variants(stem, canonicals):
    """Strip any prefix variant from the stem. `canonicals` is the
    dict {canonical: [variant, variant, ...]}.
    Returns (stripped_stem, prefix_found)."""
    stem_na = na(stem)
    for canon, variants in canonicals.items():
        for v in sorted(variants, key=len, reverse=True):
            v_na = na(v)
            if stem_na.startswith(v_na):
                return stem[len(v):], v
    return stem, ''


def _detect_augment_from_stems(aug_stem, unaug_stem, prefix):
    """Compare augmented vs unaugmented stems to find the augment.
    Handles both simple (word-initial) and compound (internal) augments.

    Before comparing, strips any prefix variant from both stems — this
    handles assimilation cases like συγχέω (1-: συγχυνν, 1+: συνεχυνν)
    where the prefix surface form differs between the two entries.
    """
    if not aug_stem or not unaug_stem or aug_stem == unaug_stem:
        return ''

    # Build canonical → variants for prefix-stripping
    canonicals = {}
    for pf, canon in PREFIXES:
        canonicals.setdefault(canon, []).append(pf)

    # Strip any prefix variant from each stem
    aug_stripped, _ = _strip_prefix_variants(aug_stem, canonicals)
    unaug_stripped, _ = _strip_prefix_variants(unaug_stem, canonicals)

    # Now compare the stripped versions
    aug_stem_use = aug_stripped if aug_stripped and unaug_stripped else aug_stem
    unaug_stem_use = unaug_stripped if aug_stripped and unaug_stripped else unaug_stem

    av = na(aug_stem_use)
    uv = na(unaug_stem_use)

    # Find common prefix between aug and unaug stems
    # (this is the preposition prefix baked into the stem)
    common_len = 0
    while (common_len < len(av) and common_len < len(uv) and
           av[common_len] == uv[common_len]):
        common_len += 1

    # After common prefix, compare what diverges
    aug_rest = av[common_len:]
    unaug_rest = uv[common_len:]

    # Syllabic augment: ε inserted (pure insertion, rest matches)
    if (aug_rest.startswith('ε') and not unaug_rest.startswith('ε') and
            aug_rest[1:] == unaug_rest):
        return aug_stem_use[common_len]

    # Syllabic augment replacing elided prefix vowel: ο/α/ι → ε
    # e.g., ἀπο+κριν → ἀπ+ε+κριν (ο drops, ε replaces it)
    if (aug_rest.startswith('ε') and unaug_rest and
            unaug_rest[0] in ('ο', 'α', 'ι') and aug_rest[1:] == unaug_rest[1:]):
        return aug_stem_use[common_len]

    # Temporal augments
    for aug_pat, unaug_pat, alen, ulen in TEMPORAL_AUGMENTS:
        if aug_rest.startswith(aug_pat) and unaug_rest.startswith(unaug_pat):
            return aug_stem_use[common_len:common_len + alen]

    # Generic: augmented stem is longer
    if len(av) > len(uv) and common_len == 0:
        # Simple syllabic augment at word start
        if av.startswith('ε') and not uv.startswith('ε'):
            return aug_stem_use[0]

    return ''


# ═══════════════════════════════════════════
# STEP 4: SPLIT FORMATIVE (tense marker)
# ═══════════════════════════════════════════

def split_formative(stem_text, tense, voice, present_stem):
    """Extract the tense formative from the end of the stem.
    The stem DB bakes the formative into the stem, so we detect it
    by comparing the tense stem to the present stem, or by known patterns.

    Returns (pure_stem, formative).
    """
    if not stem_text or tense == 'P':
        return stem_text, ''

    st_na = na(stem_text)
    ps_na = na(present_stem) if present_stem else ''

    formative = ''

    # --- Try comparison with present stem ---
    if ps_na:
        if tense == 'A' and voice in ('A', 'M'):
            formative = _extract_aor_act_formative(st_na, ps_na)
        elif tense == 'A' and voice == 'P':
            formative = _extract_aor_pass_formative(st_na, ps_na)
        elif tense == 'F' and voice in ('A', 'M'):
            formative = _extract_future_formative(st_na, ps_na)
        elif tense == 'F' and voice == 'P':
            if st_na.endswith('θησ'):
                formative = 'θησ'
        elif tense == 'X' and voice == 'A':
            if st_na.endswith('κ') and not ps_na.endswith('κ'):
                formative = 'κ'

    # --- Fallback: pattern-based detection without present stem ---
    if not formative and not ps_na:
        if tense == 'A' and voice in ('A', 'M'):
            for ending in ('σ', 'ψ', 'ξ'):
                if st_na.endswith(ending):
                    formative = ending
                    break
        elif tense == 'A' and voice == 'P':
            if st_na.endswith('θ'):
                formative = 'θ'
        elif tense == 'F' and voice in ('A', 'M'):
            for ending in ('σ', 'ψ', 'ξ'):
                if st_na.endswith(ending):
                    formative = ending
                    break
        elif tense == 'F' and voice == 'P':
            if st_na.endswith('θησ'):
                formative = 'θησ'
        elif tense == 'X' and voice == 'A':
            if st_na.endswith('κ'):
                formative = 'κ'

    if formative:
        pure = stem_text[:-len(formative)]
        actual_formative = stem_text[-len(formative):]
        return pure, actual_formative

    return stem_text, ''


def _extract_aor_act_formative(st_na, ps_na):
    """Detect 1st aorist active/middle formative: σ, ψ (labial+σ), ξ (velar+σ), κ.
    The present stem may hide the underlying consonant (e.g. ταράσσω has
    present stem ταρασσ but underlying root ταραχ-), so the ξ/ψ check
    should accept any present-stem ending as long as the aor stem clearly
    ends in ξ/ψ."""
    if st_na.endswith('σ') and not ps_na.endswith('σ'):
        return 'σ'
    if st_na.endswith('ψ') and not ps_na.endswith('ψ'):
        return 'ψ'
    if st_na.endswith('ξ') and not ps_na.endswith('ξ'):
        return 'ξ'
    if st_na.endswith('κ') and not ps_na.endswith('κ'):
        return 'κ'  # κ-aorist for -μι verbs
    # Check for σ even without present stem comparison
    if st_na.endswith('σ') and len(st_na) > len(ps_na):
        return 'σ'
    return ''


def _extract_aor_pass_formative(st_na, ps_na):
    """Detect aorist passive formative: θ."""
    if st_na.endswith('θ'):
        return 'θ'
    return ''


def _extract_future_formative(st_na, ps_na):
    """Detect future formative: σ, ψ, ξ."""
    if st_na.endswith('σ') and not ps_na.endswith('σ'):
        return 'σ'
    if st_na.endswith('ψ') and ps_na and ps_na[-1:] in 'πβφ':
        return 'ψ'
    if st_na.endswith('ξ') and ps_na and ps_na[-1:] in 'κγχ':
        return 'ξ'
    return ''


# ═══════════════════════════════════════════
# STEP 5: SPLIT ENDING (verbs)
# ═══════════════════════════════════════════

def split_ending(form, stem_val):
    """Match stem against form and return (matched_stem, ending).
    Uses accent-insensitive, case-insensitive matching.
    """
    if not stem_val:
        return form, ''

    sv_na = na(stem_val)
    fm_na = na(form)

    if fm_na.startswith(sv_na):
        return form[:len(stem_val)], form[len(stem_val):]

    # No match — whole form is stem
    return form, ''


# ═══════════════════════════════════════════
# STEP 6: SPLIT NOMINAL (nouns/adj/pronouns)
# ═══════════════════════════════════════════

NOMINAL_ENDINGS = {
    # 1st, 2nd, 3rd declension endings (accent-stripped for matching)
    ('n', 'S'): ['ος', 'ον', 'α', 'η', 'ης', 'ας', 'ις', 'υς', 'ευς', 'ωρ', 'ηρ', 'ς'],
    ('g', 'S'): ['ου', 'ης', 'ας', 'εως', 'ους', 'ος', 'α'],
    ('d', 'S'): ['ῳ', 'ῷ', 'ᾳ', 'ῃ', 'ει', 'ϊ', 'ι'],
    ('a', 'S'): ['ον', 'ην', 'αν', 'α', 'ιν', 'υν', 'εα', 'ν', 'ος'],
    ('v', 'S'): ['ε', 'η', 'α', 'ου', 'ι', 'υ', 'ος', 'ερ'],
    ('n', 'P'): ['οι', 'αι', 'α', 'ες', 'εις', 'η', 'ατα'],
    ('g', 'P'): ['ων'],
    ('d', 'P'): ['οις', 'αις', 'εσι', 'εσιν', 'σι', 'σιν', 'ψι', 'ψιν', 'ξι', 'ξιν'],
    ('a', 'P'): ['ους', 'ας', 'α', 'εις', 'ης', 'η', 'ατα', 'ες'],
    ('v', 'P'): ['οι', 'αι', 'ες', 'α', 'ατα'],
}


def split_nominal(form, case_code, number):
    """Split a noun/adjective into stem + case suffix.
    Returns (stem, suffix).
    Uses accent-insensitive comparison so accented endings match.
    """
    if not case_code or not number:
        return form, ''

    form_na = strip_accents(form)
    endings = NOMINAL_ENDINGS.get((case_code, number), [])
    for end in sorted(endings, key=len, reverse=True):
        end_na = strip_accents(end)
        if form_na.endswith(end_na) and len(form_na) > len(end_na):
            # Use the actual characters from the form for display
            split_point = len(form) - len(end)
            return form[:split_point], form[split_point:]

    return form, ''


# ═══════════════════════════════════════════
# PARTICIPLE SPLITTING
# ═══════════════════════════════════════════
# Split a participle tail into (extra_stem, ptc_marker, case_suffix).
# Strategy: tail-match the word against (marker, case_ending) pairs
# from a table keyed by (family, gender, number, case).
#
# Families:
#   A = thematic -οντ-/-ουντ- (pres act, 2nd-aor act)
#   B = σ-aorist -σαντ-/-αντ- (aor act/mid after σ, liquid)
#   C = θ-passive -θεντ-/-θεισ- (aor pass)
#   D = -μεν- family (pres mid/pass, aor mid, perf mid/pass)
#   E = perf act -οτ-/-ως-

# Endings per (family, gender, number, case) — longest marker+ending first.
# Each value is a list of (marker, ending) tuples to try in order.
PTC_ENDINGS = {
    # ─── Family A: thematic active (pres act & 2aor act) ───
    # Variants: -οντ-/-ουντ- (default/ε-contract), -ωντ- (α/ο-contract ω-fusion)
    # Masculine
    ('A','m','S','N'): [('ουν',''),('ους',''),('ων',''),('ωντ',''),('ωσ','')],
    ('A','m','S','G'): [('ουντ','ος'),('οντ','ος'),('ωντ','ος')],
    ('A','m','S','D'): [('ουντ','ι'),('οντ','ι'),('ωντ','ι')],
    ('A','m','S','A'): [('ουντ','α'),('οντ','α'),('ωντ','α')],
    ('A','m','P','N'): [('ουντ','ες'),('οντ','ες'),('ωντ','ες')],
    ('A','m','P','G'): [('ουντ','ων'),('οντ','ων'),('ωντ','ων')],
    ('A','m','P','D'): [('ουσι','ν'),('ουσι',''),('οσι','ν'),('οσι',''),('ωσι','ν'),('ωσι','')],
    ('A','m','P','A'): [('ουντ','ας'),('οντ','ας'),('ωντ','ας')],
    # Feminine
    ('A','f','S','N'): [('ουσ','α'),('ωσ','α')],
    ('A','f','S','G'): [('ουσ','ης'),('ωσ','ης')],
    ('A','f','S','D'): [('ουσ','ῃ'),('ωσ','ῃ')],
    ('A','f','S','A'): [('ουσ','αν'),('ωσ','αν')],
    ('A','f','P','N'): [('ουσ','αι'),('ωσ','αι')],
    ('A','f','P','G'): [('ουσ','ων'),('ωσ','ων')],
    ('A','f','P','D'): [('ουσ','αις'),('ωσ','αις')],
    ('A','f','P','A'): [('ουσ','ας'),('ωσ','ας')],
    # Neuter
    ('A','n','S','N'): [('ουν',''),('ον',''),('ων','')],
    ('A','n','S','G'): [('ουντ','ος'),('οντ','ος'),('ωντ','ος')],
    ('A','n','S','D'): [('ουντ','ι'),('οντ','ι'),('ωντ','ι')],
    ('A','n','S','A'): [('ουν',''),('ον',''),('ων','')],
    ('A','n','P','N'): [('ουντ','α'),('οντ','α'),('ωντ','α')],
    ('A','n','P','G'): [('ουντ','ων'),('οντ','ων'),('ωντ','ων')],
    ('A','n','P','D'): [('ουσι','ν'),('ουσι',''),('ωσι','ν')],
    ('A','n','P','A'): [('ουντ','α'),('οντ','α'),('ωντ','α')],

    # ─── Family B: σ-aorist -σαντ-/-σασ- (and liquid -αντ-/-ασ-) ───
    # Also handles -εντ-/-εισ- root aorists in active voice (like ἐπιθέντες)
    # Includes 2nd-aor thematic (-οντ-/-ουσ-) variants for forms like
    # ἐλθόντες, ἰδοῦσα, συνελθόντων, συλλαβοῦσιν
    ('B','m','S','N'): [('αντ',''),('εις',''),('ας',''),('ων',''),('ον',''),('ις',''),('υς','')],
    ('B','m','S','G'): [('αντ','ος'),('εντ','ος'),('οντ','ος')],
    ('B','m','S','D'): [('αντ','ι'),('εντ','ι'),('οντ','ι')],
    ('B','m','S','A'): [('αντ','α'),('εντ','α'),('οντ','α'),('ντ','α')],
    ('B','m','P','N'): [('αντ','ες'),('εντ','ες'),('οντ','ες'),('ντ','ες')],
    ('B','m','P','G'): [('αντ','ων'),('εντ','ων'),('οντ','ων')],
    ('B','m','P','D'): [('ασι','ν'),('ασι',''),('εισι','ν'),('εισι',''),('ουσι','ν'),('ουσι','')],
    ('B','m','P','A'): [('αντ','ας'),('εντ','ας'),('οντ','ας')],
    # Feminine (2nd-aor uses -ουσ- like present)
    ('B','f','S','N'): [('ασ','α'),('εισ','α'),('ουσ','α')],
    ('B','f','S','G'): [('ασ','ης'),('εισ','ης'),('ουσ','ης')],
    ('B','f','S','D'): [('ασ','ῃ'),('εισ','ῃ'),('ουσ','ῃ')],
    ('B','f','S','A'): [('ασ','αν'),('εισ','αν'),('ουσ','αν')],
    ('B','f','P','N'): [('ασ','αι'),('εισ','αι'),('ουσ','αι')],
    ('B','f','P','G'): [('ασ','ων'),('εισ','ων'),('ουσ','ων')],
    ('B','f','P','D'): [('ασ','αις'),('εισ','αις'),('ουσ','αις')],
    ('B','f','P','A'): [('ασ','ας'),('εισ','ας'),('ουσ','ας')],
    # Neuter
    ('B','n','S','N'): [('αν',''),('εν',''),('ον','')],
    ('B','n','S','A'): [('αν',''),('εν',''),('ον','')],
    ('B','n','S','G'): [('αντ','ος'),('εντ','ος'),('οντ','ος')],
    ('B','n','S','D'): [('αντ','ι'),('εντ','ι'),('οντ','ι')],
    ('B','n','P','N'): [('αντ','α'),('εντ','α'),('οντ','α')],
    ('B','n','P','A'): [('αντ','α'),('εντ','α'),('οντ','α')],
    ('B','n','P','G'): [('αντ','ων'),('εντ','ων'),('οντ','ων')],
    ('B','n','P','D'): [('ασι','ν'),('εισι','ν'),('ουσι','ν')],

    # ─── Family C: θ-passive -θεντ-/-θεισ- ───
    # These come AFTER the θ formative, so tails are just -εντ-/-εισ-
    ('C','m','S','N'): [('εις','')],
    ('C','m','S','G'): [('εντ','ος')],
    ('C','m','S','D'): [('εντ','ι')],
    ('C','m','S','A'): [('εντ','α')],
    ('C','m','P','N'): [('εντ','ες')],
    ('C','m','P','G'): [('εντ','ων')],
    ('C','m','P','D'): [('εισι','ν'),('εισι','')],
    ('C','m','P','A'): [('εντ','ας')],
    ('C','f','S','N'): [('εισ','α')],
    ('C','f','S','G'): [('εισ','ης')],
    ('C','f','S','D'): [('εισ','ῃ')],
    ('C','f','S','A'): [('εισ','αν')],
    ('C','f','P','N'): [('εισ','αι')],
    ('C','f','P','G'): [('εισ','ων')],
    ('C','f','P','D'): [('εισ','αις')],
    ('C','f','P','A'): [('εισ','ας')],
    ('C','n','S','N'): [('εν','')],
    ('C','n','S','A'): [('εν','')],
    ('C','n','S','G'): [('εντ','ος')],
    ('C','n','S','D'): [('εντ','ι')],
    ('C','n','P','N'): [('εντ','α')],
    ('C','n','P','A'): [('εντ','α')],
    ('C','n','P','G'): [('εντ','ων')],
    ('C','n','P','D'): [('εισι','ν')],

    # ─── Family D: -μεν- (pres mid/pass, aor mid, perf mid/pass) ───
    # Marker includes the thematic vowel: ομεν, ουμεν (ε-contract), αμεν (α-contract, σ-aor mid), μεν (perf m/p)
    # Inflected with 2nd-decl (m/n) and 1st-decl (f) adj endings
    ('D','m','S','N'): [('ουμεν','ος'),('ομεν','ος'),('αμεν','ος'),('μεν','ος')],
    ('D','m','S','G'): [('ουμεν','ου'),('ομεν','ου'),('αμεν','ου'),('μεν','ου')],
    ('D','m','S','D'): [('ουμεν','ῳ'),('ομεν','ῳ'),('αμεν','ῳ'),('μεν','ῳ')],
    ('D','m','S','A'): [('ουμεν','ον'),('ομεν','ον'),('αμεν','ον'),('μεν','ον')],
    ('D','m','P','N'): [('ουμεν','οι'),('ομεν','οι'),('αμεν','οι'),('μεν','οι')],
    ('D','m','P','G'): [('ουμεν','ων'),('ομεν','ων'),('αμεν','ων'),('μεν','ων')],
    ('D','m','P','D'): [('ουμεν','οις'),('ομεν','οις'),('αμεν','οις'),('μεν','οις')],
    ('D','m','P','A'): [('ουμεν','ους'),('ομεν','ους'),('αμεν','ους'),('μεν','ους')],
    # Feminine (1st decl)
    ('D','f','S','N'): [('ουμεν','η'),('ομεν','η'),('αμεν','η'),('μεν','η')],
    ('D','f','S','G'): [('ουμεν','ης'),('ομεν','ης'),('αμεν','ης'),('μεν','ης')],
    ('D','f','S','D'): [('ουμεν','ῃ'),('ομεν','ῃ'),('αμεν','ῃ'),('μεν','ῃ')],
    ('D','f','S','A'): [('ουμεν','ην'),('ομεν','ην'),('αμεν','ην'),('μεν','ην')],
    ('D','f','P','N'): [('ουμεν','αι'),('ομεν','αι'),('αμεν','αι'),('μεν','αι')],
    ('D','f','P','G'): [('ουμεν','ων'),('ομεν','ων'),('αμεν','ων'),('μεν','ων')],
    ('D','f','P','D'): [('ουμεν','αις'),('ομεν','αις'),('αμεν','αις'),('μεν','αις')],
    ('D','f','P','A'): [('ουμεν','ας'),('ομεν','ας'),('αμεν','ας'),('μεν','ας')],
    # Neuter
    ('D','n','S','N'): [('ουμεν','ον'),('ομεν','ον'),('αμεν','ον'),('μεν','ον')],
    ('D','n','S','A'): [('ουμεν','ον'),('ομεν','ον'),('αμεν','ον'),('μεν','ον')],
    ('D','n','S','G'): [('ουμεν','ου'),('ομεν','ου'),('αμεν','ου'),('μεν','ου')],
    ('D','n','S','D'): [('ουμεν','ῳ'),('ομεν','ῳ'),('αμεν','ῳ'),('μεν','ῳ')],
    ('D','n','P','N'): [('ουμεν','α'),('ομεν','α'),('αμεν','α'),('μεν','α')],
    ('D','n','P','A'): [('ουμεν','α'),('ομεν','α'),('αμεν','α'),('μεν','α')],
    ('D','n','P','G'): [('ουμεν','ων'),('ομεν','ων'),('αμεν','ων'),('μεν','ων')],
    ('D','n','P','D'): [('ουμεν','οις'),('ομεν','οις'),('αμεν','οις'),('μεν','οις')],

    # ─── Family E: perf act -οτ-/-ως-/-υι- ───
    ('E','m','S','N'): [('ως','')],
    ('E','m','S','G'): [('οτ','ος'),('κοτ','ος')],
    ('E','m','S','D'): [('οτ','ι'),('κοτ','ι')],
    ('E','m','S','A'): [('οτ','α'),('κοτ','α')],
    ('E','m','P','N'): [('οτ','ες'),('κοτ','ες')],
    ('E','m','P','G'): [('οτ','ων'),('κοτ','ων')],
    ('E','m','P','D'): [('οσι','ν'),('οσι','')],
    ('E','m','P','A'): [('οτ','ας'),('κοτ','ας')],
    ('E','f','S','N'): [('υι','α')],
    ('E','f','S','G'): [('υι','ης')],
    ('E','f','S','D'): [('υι','ῃ')],
    ('E','f','S','A'): [('υι','αν')],
    ('E','f','P','N'): [('υι','αι')],
    ('E','n','S','N'): [('ος',''),('ος','')],
    ('E','n','S','A'): [('ος',''),('ος','')],
    ('E','n','S','G'): [('οτ','ος')],
    ('E','n','P','N'): [('οτ','α')],
}


def choose_ptc_family(tense, voice):
    """Determine which participle family this form belongs to."""
    if tense == 'A' and voice == 'P':
        return 'C'  # aorist passive -θεντ-
    if tense == 'A' and voice == 'M':
        return 'D'  # aorist middle uses -μεν-
    if tense == 'A' and voice == 'A':
        return 'B'  # σ-aorist active (or liquid -αντ-, root -εντ-)
    if tense == 'X' and voice == 'A':
        return 'E'  # perfect active -οτ-
    if tense in ('X', 'Y') and voice in ('M', 'P'):
        return 'D'  # perfect mid/pass -μεν-
    if tense == 'P' and voice in ('M', 'P'):
        return 'D'  # present mid/pass -μεν-
    # Present/imperfect active (though imperfect has no participle), future
    return 'A'  # thematic -οντ-


def split_participle(tail, tense, voice, case, number, gender):
    """Split participle tail into (extra_stem, ptc_marker, case_ending).
    Uses accent-insensitive tail matching.
    Returns ('', '', '') if no split found.
    """
    if not tail or not case or not number or not gender:
        return '', '', ''

    case_map = {'N':'N','G':'G','D':'D','A':'A','V':'N'}
    case_key = case_map.get(case, case)
    family = choose_ptc_family(tense, voice)
    candidates = PTC_ENDINGS.get((family, gender, number, case_key), [])

    tail_na = na(tail)

    # Try longest combined length first, then as listed
    sorted_cands = sorted(candidates, key=lambda p: -(len(p[0]) + len(p[1])))
    for marker, ending in sorted_cands:
        combined = marker + ending
        if not combined:
            continue
        combined_na = na(combined)
        if tail_na.endswith(combined_na):
            split1 = len(tail) - len(combined_na)
            split2 = split1 + len(na(marker))
            return tail[:split1], tail[split1:split2], tail[split2:]

    return '', '', ''


# ═══════════════════════════════════════════
# REDUPLICATION DETECTION
# ═══════════════════════════════════════════

def split_reduplication(stem_text, tense, present_stem):
    """Detect perfect/pluperfect reduplication at the start of the stem.
    Returns (reduplication, remainder).
    """
    if tense not in ('X', 'Y'):
        return '', stem_text

    if not stem_text or len(stem_text) < 2:
        return '', stem_text

    # Common reduplication: first consonant + ε
    st_na = na(stem_text)
    ps_na = na(present_stem) if present_stem else ''

    if len(st_na) >= 2 and st_na[1] == 'ε':
        # Check if the first char matches the present stem's first char
        if ps_na and st_na[0] == ps_na[0]:
            return stem_text[:2], stem_text[2:]
        # Or if it's a recognizable consonant reduplication
        if st_na[0] in 'βγδζθκλμνπρστφχψ':
            return stem_text[:2], stem_text[2:]

    return '', stem_text


# ═══════════════════════════════════════════
# MAIN DECOMPOSE FUNCTION
# ═══════════════════════════════════════════

def decompose_verb(form, lemma, parsing, pos, stems_dict):
    """Full verb decomposition pipeline.
    Returns dict with keys: pfx, aug, rdp, stm, frm, ve, suf, cs, prs.
    """
    tense  = parsing[1] if len(parsing) > 1 and parsing[1] != '-' else None
    voice  = parsing[2] if len(parsing) > 2 and parsing[2] != '-' else None
    mood   = parsing[3] if len(parsing) > 3 and parsing[3] != '-' else None
    case   = parsing[4] if len(parsing) > 4 and parsing[4] != '-' else None
    number = parsing[5] if len(parsing) > 5 and parsing[5] != '-' else None
    gender_code = parsing[6] if len(parsing) > 6 and parsing[6] != '-' else None
    gender = {'M':'m','F':'f','N':'n'}.get(gender_code)

    clean = clean_surface(form)

    # 1. Resolve stems from DB
    stem_val, aug_stem, unaug_stem, present_stem = resolve_stems(
        stems_dict, tense, voice)

    # For augmented tenses in indicative, use augmented stem for matching
    if mood == 'I' and tense in ('A', 'I', 'Y') and aug_stem:
        match_stem = aug_stem
    else:
        match_stem = stem_val

    # 2. Split prefix
    pfx, remainder = split_prefix(clean, match_stem, present_stem, lemma)

    # If prefix found, also strip it from match_stem for later matching
    match_stem_inner = match_stem
    if pfx and match_stem:
        pfx_na = na(pfx)
        ms_na = na(match_stem)
        if ms_na.startswith(pfx_na):
            match_stem_inner = match_stem[len(pfx):]

    # 3. Split augment
    aug, remainder = split_augment(
        remainder, pfx, aug_stem, unaug_stem, lemma, tense, voice, mood)

    # Also strip augment from match_stem_inner for stem matching
    if aug and match_stem_inner:
        aug_na_val = na(aug)
        msi_na = na(match_stem_inner)
        if msi_na.startswith(aug_na_val):
            match_stem_inner = match_stem_inner[len(aug):]

    # 4. Match stem and get ending
    matched, ending = split_ending(remainder, match_stem_inner)

    # 5. Split formative from the matched stem
    pure_stem, formative = split_formative(matched, tense, voice, present_stem)

    # 6. Split reduplication
    rdp, pure_stem = split_reduplication(pure_stem, tense, present_stem)

    # 7. For participles, reclassify ending as case suffix
    case_map = {'N': 'n', 'G': 'g', 'D': 'd', 'A': 'a', 'V': 'v'}
    cs = case_map.get(case)

    # Determine what the morpheme pieces are for this word
    pmk_val = ''  # participle morpheme kernel (middle of ptc ending)
    suf_val = ''
    ve_val = ''

    if mood == 'P' and cs and gender:
        # Participle: tail-match to get marker + case ending
        if ending:
            extra, ptc_marker, suf_val = split_participle(
                ending, tense, voice, case, number, gender)
            if ptc_marker:
                if extra:
                    pure_stem = (pure_stem or '') + extra
                pmk_val = ptc_marker
            else:
                # Tail too short — retry with stem + ending
                # (happens when stem DB over-extends into the ptc marker,
                # e.g. δίδωμι 1-: διδο absorbs the 'ο' that belongs to -ους marker)
                combined = (pure_stem or '') + ending
                extra2, ptc_marker2, suf_val2 = split_participle(
                    combined, tense, voice, case, number, gender)
                if ptc_marker2:
                    pure_stem = extra2
                    pmk_val = ptc_marker2
                    suf_val = suf_val2
                else:
                    suf_val = ending
        else:
            # Stem-match failed; the whole pure_stem is the tail
            tail = pure_stem or ''
            extra, ptc_marker, suf_val = split_participle(
                tail, tense, voice, case, number, gender)
            if ptc_marker:
                pure_stem = extra
                pmk_val = ptc_marker
    else:
        # Non-participle verb
        ve_val = ending

    # ═══ THEMATIC VOWEL TRANSFER ═══
    # σα, κα/κε, θη/θε are the traditional tense formatives.
    # If the formative ends in a thematic consonant (σ κ θ ψ ξ)
    # and the next piece starts with a thematic vowel, pull it in.
    formative, pmk_val, ve_val = _transfer_thematic_vowel(
        formative, pmk_val, ve_val)

    # ═══ BUILD LEGACY KEYS ═══
    result = {}
    if pfx: result['pfx'] = pfx
    if aug: result['aug'] = aug
    if rdp: result['rdp'] = rdp
    if pure_stem: result['stm'] = pure_stem
    if formative: result['frm'] = formative
    if pmk_val: result['ptc'] = pmk_val
    if ve_val: result['ve'] = ve_val
    if suf_val: result['suf'] = suf_val
    if cs: result['cs'] = cs

    # ═══ BUILD SEGS (channel-aware overlap-capable segmentation) ═══
    # Keep ve (verb ending) separate from suf (case suffix) so the End
    # layer only colors verb endings and the Case layer only colors nominal/ptc suffixes.
    pieces = {
        'pfx': pfx, 'aug': aug, 'rdp': rdp, 'stm': pure_stem,
        'frm': formative, 'pmk': pmk_val, 've': ve_val, 'suf': suf_val,
    }
    channels = build_channels(clean, pieces, cs)
    result['segs'] = segment_channels(clean, channels)

    return result


def _transfer_thematic_vowel(formative, pmk, ve):
    """If formative ends in σ/κ/θ/ψ/ξ and the next piece starts with
    α/ε/η/ο/ω, pull that vowel into the formative.
    This gives traditional σα/σε/κα/κε/θη/θε formatives.
    """
    if not formative:
        return formative, pmk, ve
    THEMATIC_CONS = set('σκθψξ')
    THEMATIC_VOW = set('αεηοω')
    last_cons = na(formative[-1:])
    if last_cons not in THEMATIC_CONS:
        return formative, pmk, ve
    # Try pmk first, then ve
    if pmk:
        first_vow = na(pmk[:1])
        if first_vow in THEMATIC_VOW:
            return formative + pmk[0], pmk[1:], ve
    elif ve:
        first_vow = na(ve[:1])
        if first_vow in THEMATIC_VOW:
            return formative + ve[0], pmk, ve[1:]
    return formative, pmk, ve


def decompose_nominal(form, parsing):
    """Decompose a noun/adjective/pronoun into stem + case suffix."""
    case_map = {'N': 'n', 'G': 'g', 'D': 'd', 'A': 'a', 'V': 'v'}
    number_val = parsing[5] if len(parsing) > 5 and parsing[5] != '-' else None
    case_val = case_map.get(parsing[4]) if len(parsing) > 4 else None

    clean = clean_surface(form)
    stem, suf = split_nominal(clean, case_val, number_val)

    result = {}
    if stem: result['stm'] = stem
    cs_for_segs = None
    if suf:
        result['suf'] = suf
        result['cs'] = case_val
        cs_for_segs = case_val

    # Build segs for channel-aware rendering
    pieces = {'stm': stem, 'suf': suf}
    channels = build_channels(clean, pieces, cs_for_segs)
    result['segs'] = segment_channels(clean, channels)

    return result
