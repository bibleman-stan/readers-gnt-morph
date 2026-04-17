#!/usr/bin/env python3
"""
inflect_gloss.py — Inflect a bare English verb gloss to match Greek
tense / voice / mood at build time.

Used by generate_chapter.py to precompute one inflected gloss per
verb form before chapter JSON is written. The browser then just reads
the precomputed string — no client-side inflection logic.

Public entry point: inflect_gloss(bare_gloss, tvm, lemma=None)
  bare_gloss: the lemma's English gloss (e.g. "choose", "set apart",
              "I am assembled together with")
  tvm:        3-char string of MorphGNT tense + voice + mood codes
              (e.g. "AAI" = aorist active indicative)
  lemma:      Greek lemma (used for deponent detection / overrides)

Returns the inflected English string, or the bare gloss if inflection
isn't applicable / safe.
"""
import re

# ═══════════════════════════════════════════
# IRREGULAR ENGLISH VERB FORMS
# ═══════════════════════════════════════════
# Map: bare verb -> (simple past, past participle).
# For regular verbs, simple past == past participle == verb + "ed"
# (with spelling rules in _regular_past below).
# This table only needs entries that appear in NT lemma glosses.
IRREGULAR = {
    'be':         ('was', 'been'),
    'become':     ('became', 'become'),
    'begin':      ('began', 'begun'),
    'bring':      ('brought', 'brought'),
    'build':      ('built', 'built'),
    'buy':        ('bought', 'bought'),
    'catch':      ('caught', 'caught'),
    'choose':     ('chose', 'chosen'),
    'come':       ('came', 'come'),
    'cost':       ('cost', 'cost'),
    'cut':        ('cut', 'cut'),
    'do':         ('did', 'done'),
    'draw':       ('drew', 'drawn'),
    'drink':      ('drank', 'drunk'),
    'drive':      ('drove', 'driven'),
    'eat':        ('ate', 'eaten'),
    'fall':       ('fell', 'fallen'),
    'feel':       ('felt', 'felt'),
    'find':       ('found', 'found'),
    'fly':        ('flew', 'flown'),
    'forget':     ('forgot', 'forgotten'),
    'forgive':    ('forgave', 'forgiven'),
    'forsake':    ('forsook', 'forsaken'),
    'get':        ('got', 'gotten'),
    'give':       ('gave', 'given'),
    'go':         ('went', 'gone'),
    'grow':       ('grew', 'grown'),
    'have':       ('had', 'had'),
    'hear':       ('heard', 'heard'),
    'hide':       ('hid', 'hidden'),
    'hold':       ('held', 'held'),
    'keep':       ('kept', 'kept'),
    'know':       ('knew', 'known'),
    'lay':        ('laid', 'laid'),
    'lead':       ('led', 'led'),
    'leave':      ('left', 'left'),
    'lend':       ('lent', 'lent'),
    'let':        ('let', 'let'),
    'lie':        ('lay', 'lain'),
    'lose':       ('lost', 'lost'),
    'make':       ('made', 'made'),
    'mean':       ('meant', 'meant'),
    'meet':       ('met', 'met'),
    'pay':        ('paid', 'paid'),
    'put':        ('put', 'put'),
    'read':       ('read', 'read'),
    'rise':       ('rose', 'risen'),
    'run':        ('ran', 'run'),
    'say':        ('said', 'said'),
    'see':        ('saw', 'seen'),
    'sell':       ('sold', 'sold'),
    'send':       ('sent', 'sent'),
    'set':        ('set', 'set'),
    'shake':      ('shook', 'shaken'),
    'sit':        ('sat', 'sat'),
    'sleep':      ('slept', 'slept'),
    'speak':      ('spoke', 'spoken'),
    'spend':      ('spent', 'spent'),
    'stand':      ('stood', 'stood'),
    'take':       ('took', 'taken'),
    'teach':      ('taught', 'taught'),
    'tell':       ('told', 'told'),
    'think':      ('thought', 'thought'),
    'throw':      ('threw', 'thrown'),
    'understand': ('understood', 'understood'),
    'win':        ('won', 'won'),
    'write':      ('wrote', 'written'),
    'arise':      ('arose', 'arisen'),
    'bear':       ('bore', 'borne'),
    'bind':       ('bound', 'bound'),
    'flee':       ('fled', 'fled'),
    'feed':       ('fed', 'fed'),
    'overcome':   ('overcame', 'overcome'),
    'spread':     ('spread', 'spread'),
    'tear':       ('tore', 'torn'),
    'wake':       ('woke', 'woken'),
    'withdraw':   ('withdrew', 'withdrawn'),
    'forbid':     ('forbade', 'forbidden'),
    'forsee':     ('foresaw', 'foreseen'),
    'understand': ('understood', 'understood'),
    'beat':       ('beat', 'beaten'),
    'strike':     ('struck', 'struck'),
}


# ═══════════════════════════════════════════
# REGULAR-VERB SPELLING RULES
# ═══════════════════════════════════════════

def _regular_past(verb):
    """Apply standard English -ed inflection for regular verbs."""
    v = verb.lower()
    if v.endswith('e'):
        return v + 'd'                                    # bake -> baked
    if re.search(r'[^aeiou]y$', v):
        return v[:-1] + 'ied'                             # try -> tried
    # Short vowel + single consonant at end: stop -> stopped, ban -> banned
    # Requires SINGLE vowel: a non-vowel before the final v-c pair, so
    # "hear" (v-v-c) does not double, while "ban" (c-v-c) does.
    if re.fullmatch(r'[a-z]{2,4}', v) \
       and re.search(r'[^aeiou][aeiou][bcdfgklmnprstvz]$', v):
        return v + v[-1] + 'ed'
    return v + 'ed'


def _past_simple(verb):
    """Return English simple-past form of a bare verb."""
    v = verb.lower()
    if v in IRREGULAR:
        return IRREGULAR[v][0]
    return _regular_past(v)


def _past_participle(verb):
    """Return English past-participle form of a bare verb."""
    v = verb.lower()
    if v in IRREGULAR:
        return IRREGULAR[v][1]
    return _regular_past(v)


def _present_third_singular(verb):
    """Return English present 3rd-singular form (for "is X-ed" passive)."""
    v = verb.lower()
    if v in ('be', 'is', 'am', 'are'):
        return 'is'
    if v.endswith('s') or v.endswith('x') or v.endswith('z') \
       or v.endswith('ch') or v.endswith('sh'):
        return v + 'es'
    if re.search(r'[^aeiou]y$', v):
        return v[:-1] + 'ies'
    return v + 's'


# ═══════════════════════════════════════════
# LEMMA OVERRIDES
# ═══════════════════════════════════════════
# A pre-tabulated (lemma, tvm) -> inflected gloss for verbs whose
# Dodson lexicon entry is misleading or stative, where naive
# inflection would emit broken or wrong English.
#
# Format: { lemma: { tvm_pattern: inflected_form, ... } }
# tvm_pattern can be a full 3-char code or a wildcard '*' for catch-all.
# Most-specific match wins (full code > wildcard).
LEMMA_OVERRIDES = {
    # εἰμί — full suppletive paradigm; bare lexicon "I am" is useless for inflection
    'εἰμί': {
        'PAI': 'is',  'IAI': 'was', 'FMI': 'will be',
        'PAS': 'be',  'PAO': 'might be', 'PAN': 'to be', 'PAP': 'being',
    },
    # οἶδα — perfect form, present meaning
    'οἶδα': {
        'XAI': 'know', 'YAI': 'knew',
        'XAS': 'know', 'XAN': 'to know', 'XAP': 'knowing',
    },
    # δύναμαι — stative gloss "I am able"; deponent
    'δύναμαι': {
        'PMI': 'is able', 'IMI': 'was able',
        'API': 'was able', 'FMI': 'will be able',
        'PMN': 'to be able', 'PMP': 'being able',
    },
    # μέλλω — gloss is already "I am about to" (a phrase)
    'μέλλω': {
        'PAI': 'is about to', 'IAI': 'was about to',
        'FAI': 'will be about to', 'PAP': 'being about to',
    },
    # δεῖ — impersonal "it is necessary"
    'δεῖ': {
        'PAI': 'it is necessary', 'IAI': 'it was necessary',
        'PAN': 'to be necessary', 'PAP': 'being necessary',
    },
    # συναλίζομαι — Dodson "I am assembled together with" → unwieldy
    'συναλίζομαι': {
        '*':   'meet with',
        'PMP': 'meeting with',
    },
    # ἔρχομαι — deponent ("come"), aorist passive form ἦλθον is active in meaning
    'ἔρχομαι': {
        'AAI': 'came', 'API': 'came', 'AMI': 'came',
        'IMI': 'was coming',
    },
    # γίνομαι — deponent ("become / happen")
    'γίνομαι': {
        'AMI': 'became', 'API': 'became',
        'IMI': 'was becoming',
    },
    # πορεύομαι — deponent ("go")
    'πορεύομαι': {
        'AMI': 'went', 'API': 'went',
        'IMI': 'was going',
    },
    # ἀποκρίνομαι — deponent ("answer"); aorist API is morphologically
    # passive but semantically active
    'ἀποκρίνομαι': {
        'AMI': 'answered', 'API': 'answered',
        'IMI': 'was answering',
    },
    # βούλομαι — deponent ("want / wish")
    'βούλομαι': {
        'API': 'wanted', 'AMI': 'wanted', 'IMI': 'was wanting',
    },
    # ἀφορίζω — phrasal: "set apart"; "set" is its own past
    'ἀφορίζω': {
        '*': 'set apart',
    },
    # ἀναλαμβάνω — phrasal: "take up"; head verb is "take" → took/taken
    'ἀναλαμβάνω': {
        'AAI': 'took up', 'API': 'was taken up', 'AMI': 'took up',
        'PAI': 'takes up', 'PAN': 'to take up', 'PAP': 'taking up',
    },
    # ἐπικαλέω / ἐπικαλέομαι — phrasal: "call upon"
    'ἐπικαλέω': {
        'AMI': 'called upon', 'AAI': 'called upon', 'API': 'was called upon',
    },
    # ἀποθνῄσκω — Dodson gloss is "I am dying" (stative); aorist must
    # be "died", not "was dying"
    'ἀποθνῄσκω': {
        'AAI': 'died', 'PAI': 'dies', 'IAI': 'was dying',
        'PAN': 'to die', 'PAP': 'dying',
    },
    # γίνομαι alt form — already covered above
    # κάθημαι — deponent stative ("sit")
    'κάθημαι': {
        'PMI': 'sits', 'IMI': 'was sitting',
        'PMP': 'sitting',
    },
    # φοβέομαι — deponent ("fear / be afraid")
    'φοβέομαι': {
        'API': 'feared', 'AMI': 'feared',
        'IMI': 'was fearing',
    },
}


# ═══════════════════════════════════════════
# GLOSS NORMALIZATION
# ═══════════════════════════════════════════

# Auxiliary tokens that signal a "stative" gloss shape ("be assembled",
# "am born") whose remainder is already a past-participle phrase.
STATIVE_AUX = {'be', 'am', 'is', 'are', 'was', 'were', 'being'}

# Tokens that indicate an impersonal-construction gloss ("it is necessary").
# These should not have head-verb inflection applied.
IMPERSONAL_LEAD = {'it'}


def _strip_lead_article(gloss):
    """Remove leading 'I ', 'a ', 'an ', 'the ' from a Dodson gloss."""
    g = gloss.strip()
    for lead in ('I ', 'a ', 'an ', 'the '):
        if g.startswith(lead):
            return g[len(lead):]
    return g


def _classify(gloss):
    """Classify a normalized gloss for inflection routing.

    Returns one of:
      ('verbal',    head_verb, tail)       — head verb + remaining tokens
      ('stative',   adjpart_phrase)        — auxiliary stripped, e.g.
                                             "assembled together with"
      ('impersonal', whole_phrase)         — "it is necessary" style
      ('empty',     '')                    — empty / whitespace
    """
    g = gloss.strip()
    if not g:
        return ('empty', '')

    parts = g.split()
    head = parts[0].lower()

    if head in IMPERSONAL_LEAD:
        return ('impersonal', g)

    if head in STATIVE_AUX and len(parts) >= 2:
        return ('stative', ' '.join(parts[1:]))

    # Single-word or phrasal verb (head-verb inflection possible)
    return ('verbal', parts[0], ' '.join(parts[1:]))


# ═══════════════════════════════════════════
# DEPONENT DETECTION
# ═══════════════════════════════════════════

def _is_deponent(lemma, gloss):
    """A lemma is treated as deponent if it ends in -μαι and its gloss
    (after stripping leading 'I ') starts with an active English verb
    (not 'am X-ed', 'be X-ed', etc.).

    Used to decide whether to treat a passive-morphology aorist as
    semantically active (deponent: 'answered') vs passive ('was answered').
    """
    if not lemma or not lemma.endswith(('μαι',)):
        return False
    g = _strip_lead_article(gloss).strip().lower()
    if not g:
        return False
    first = g.split()[0]
    return first not in STATIVE_AUX


# ═══════════════════════════════════════════
# CORE INFLECTION DISPATCH
# ═══════════════════════════════════════════

def _phrasal_past_simple(head, tail):
    return _past_simple(head) + ((' ' + tail) if tail else '')

def _phrasal_past_participle(head, tail):
    return _past_participle(head) + ((' ' + tail) if tail else '')

def _phrasal_present(head, tail):
    return head + ((' ' + tail) if tail else '')

def _phrasal_3sg(head, tail):
    return _present_third_singular(head) + ((' ' + tail) if tail else '')


def _inflect_indicative(t, v, m, head, tail, deponent=False):
    """Inflect a verbal-shape gloss for an indicative form."""
    # Treat middle as active in English by default; treat passive of
    # deponents as active too.
    effective_voice = v
    if v == 'M':
        effective_voice = 'A'
    if v == 'P' and deponent:
        effective_voice = 'A'

    if t == 'A':  # Aorist
        if effective_voice == 'A':
            return _phrasal_past_simple(head, tail)
        return 'was ' + _phrasal_past_participle(head, tail)
    if t == 'I':  # Imperfect
        if effective_voice == 'A':
            return 'was ' + _phrasal_present(head, tail) + 'ing' \
                   if False else _imperfect_active(head, tail)
        return 'was being ' + _phrasal_past_participle(head, tail)
    if t == 'F':  # Future
        if effective_voice == 'A':
            return 'will ' + _phrasal_present(head, tail)
        return 'will be ' + _phrasal_past_participle(head, tail)
    if t == 'P':  # Present
        if effective_voice == 'A':
            return _phrasal_present(head, tail)
        return 'is ' + _phrasal_past_participle(head, tail)
    if t == 'X':  # Perfect
        if effective_voice == 'A':
            return 'have ' + _phrasal_past_participle(head, tail)
        return 'has been ' + _phrasal_past_participle(head, tail)
    if t == 'Y':  # Pluperfect
        if effective_voice == 'A':
            return 'had ' + _phrasal_past_participle(head, tail)
        return 'had been ' + _phrasal_past_participle(head, tail)
    return _phrasal_present(head, tail)


def _imperfect_active(head, tail):
    """Build 'was X-ing' form, applying English -ing spelling rules."""
    h = head.lower()
    if h.endswith('ie'):
        ing = h[:-2] + 'ying'
    elif h.endswith('ee'):
        ing = h + 'ing'
    elif h.endswith('e'):
        ing = h[:-1] + 'ing'
    elif re.fullmatch(r'[a-z]{2,4}', h) \
         and re.search(r'[^aeiou][aeiou][bcdfgklmnprstvz]$', h):
        ing = h + h[-1] + 'ing'
    else:
        ing = h + 'ing'
    return 'was ' + ing + ((' ' + tail) if tail else '')


def _inflect_stative(t, v, m, adjpart_phrase):
    """Inflect a stative-shape gloss ("be assembled with").
    The adjpart_phrase is what comes after the auxiliary; we just
    prefix the appropriate temporal aux.
    """
    if t == 'A':  return 'was ' + adjpart_phrase
    if t == 'I':  return 'was ' + adjpart_phrase
    if t == 'F':  return 'will be ' + adjpart_phrase
    if t == 'P':  return 'is ' + adjpart_phrase
    if t == 'X':  return 'has been ' + adjpart_phrase
    if t == 'Y':  return 'had been ' + adjpart_phrase
    return 'is ' + adjpart_phrase


# ═══════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════

def inflect_gloss(bare_gloss, tvm, lemma=None):
    """Inflect a bare English verb gloss to match Greek tense/voice/mood.

    Returns the inflected string. If inflection isn't applicable
    (non-indicative mood, empty gloss, classification miss), returns
    a sensible fallback (often the bare gloss itself).
    """
    if not bare_gloss:
        return bare_gloss
    if not tvm or len(tvm) < 3:
        return bare_gloss

    t, v, m = tvm[0], tvm[1], tvm[2]

    # Step 1: lemma override (most-specific match wins)
    if lemma and lemma in LEMMA_OVERRIDES:
        rules = LEMMA_OVERRIDES[lemma]
        if tvm in rules:
            return rules[tvm]
        if '*' in rules:
            return rules['*']
        # Fall through to general inflection if no matching pattern

    # Step 2: only inflect indicative mood for v1
    # (subjunctive, optative, imperative, infinitive, participle keep bare)
    if m != 'I':
        return bare_gloss

    # Step 3: classify normalized gloss
    norm = _strip_lead_article(bare_gloss)
    cls = _classify(norm)

    if cls[0] == 'empty':
        return bare_gloss

    if cls[0] == 'impersonal':
        # Don't try to inflect "it is necessary" structurally —
        # if no override matched, leave bare.
        return bare_gloss

    if cls[0] == 'stative':
        # cls = ('stative', adjpart_phrase)
        return _inflect_stative(t, v, m, cls[1])

    if cls[0] == 'verbal':
        # cls = ('verbal', head, tail)
        head = cls[1]
        # Safeguard: if head doesn't look like an English verb (contains
        # punctuation, parens, digits), bail out rather than emit garbage.
        if not re.fullmatch(r'[a-zA-Z]+', head):
            return bare_gloss
        deponent = _is_deponent(lemma, bare_gloss)
        return _inflect_indicative(t, v, m, head, cls[2], deponent=deponent)

    return bare_gloss


if __name__ == '__main__':
    # Quick smoke from CLI: python src/inflect_gloss.py
    cases = [
        ('choose', 'AAI', 'ἐκλέγομαι'),
        ('choose', 'AMI', 'ἐκλέγομαι'),
        ('take up', 'API', 'ἀναλαμβάνω'),
        ('answer', 'API', 'ἀποκρίνομαι'),
        ('I am', 'IAI', 'εἰμί'),
        ('hear', 'PAI', 'ἀκούω'),
        ('hear', 'IAI', 'ἀκούω'),
        ('hear', 'FMI', 'ἀκούω'),
        ('write', 'XPI', 'γράφω'),
    ]
    for g, t, l in cases:
        print(f'{l:18s} {t}  "{g}"  ->  "{inflect_gloss(g, t, l)}"')
