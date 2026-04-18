#!/usr/bin/env python3
"""
chapter_review.py — Parallel Haiku/Sonnet/Opus reviews of chapter JSON.

Codifies the "reviewer horde" pattern that's been hand-dispatched via Agent
tool calls in prior sessions. Given a list of chapters, fans out one review
per chapter in parallel, writes the markdown response to disk, and prints a
summary. The shared system prompt is cached (5-min TTL) so the first request
pays the cache-write premium and the other N-1 read at ~0.1× cost.

Usage:
  # Review two specific chapters with Haiku (default tier)
  PYTHONIOENCODING=utf-8 python src/chapter_review.py romans/3 galatians/5

  # Sample-based sweep: 2 chapters per book, all 27 books
  PYTHONIOENCODING=utf-8 python src/chapter_review.py --all-books --sample 2

  # One book, full sweep, Sonnet tier
  PYTHONIOENCODING=utf-8 python src/chapter_review.py --book revelation --model sonnet

  # Opus-tier adversarial pass on three specific chapters
  PYTHONIOENCODING=utf-8 python src/chapter_review.py --model opus \\
      hebrews/11 john/1 revelation/5 --tag opus-deep-dive

Output goes under reviews/YYYY-MM-DD-<tag>/ as <book>-<chapter>.md plus a
_summary.md aggregating counts.

Environment:
  ANTHROPIC_API_KEY — required.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import random
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from books import BOOKS

try:
    import anthropic
except ImportError:
    print('ERROR: anthropic SDK not installed. Run: pip install anthropic',
          file=sys.stderr)
    sys.exit(2)

_REPO_ROOT = os.path.dirname(_HERE)

MODELS = {
    'haiku':  'claude-haiku-4-5',
    'sonnet': 'claude-sonnet-4-6',
    'opus':   'claude-opus-4-7',
}

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — cached. Every chapter review shares this verbatim, so the
# first request pays the write premium and the others read at ~0.1×.
# ═══════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are a reviewer for a Greek New Testament morpheme-reader published at morph.gnt-reader.com. The project decomposes Greek words into colored morphological pieces and attaches English glosses — inflected for finite verbs (e.g. ἐξελέξατο → "chose", not "choose"), bare dictionary form for other moods.

Your job is to scan one chapter's JSON data and flag gloss problems that hurt the student reading the text. Be terse. Be specific. Skip non-problems.

# JSON schema reminders

Each word entry may have these fields:
- `lem` — Greek lemma (dictionary form)
- `prs` — parse string (e.g. "aor mid ind 3 sg", "pres act ptc nom sg masc")
- `txt` — surface form as it appears in the text
- `tvm` — 3-char tense/voice/mood code for verbs (e.g. "AAI", "APP", "PAS")
- `igl` — **inflected English gloss** — the rendered gloss for indicative verbs ("chose", "had been written", "will receive"). This is the primary thing to review.

Separately, the `LEX` table at the end maps `lem → {gl: <bare dictionary gloss>, f: <NT frequency>}`. The `gl` is the fallback gloss when there's no `igl`.

# What to flag (in order of importance)

1. **Wrong English inflection** — e.g. "canned" for δύναμαι APS, "highlied" for ὑπερυψόω, "heared" for ἀκούω AAI, "writed" for γράφω PAI. These are inflection-engine bugs. Report the form and the expected correct rendering.
2. **Semantic errors** in the bare gloss — e.g. πνεῦμα glossed as "wind" when every NT reader expects "spirit"; λόγος as "word" when the passage clearly means "account" or "reason". Only flag when the lexicon default is actively misleading in modern English.
3. **Etymologically leaky glosses** — where the English gloss is a transliteration of the Greek root that isn't idiomatic English. e.g. glossing δύναμις as "dynamis" or ἀγάπη as "agape" when "power" and "love" would serve the reader better.
4. **Archaic or awkward English** — "betwixt", "verily", unnecessary "thee/thou" — only flag if it trips a modern reader.
5. **Missing `igl` on an indicative verb** where one would obviously help. Most indicatives now have `igl`; report any conspicuous gaps.

# What NOT to flag

- **Participles without `igl`** — participle glosses ARE stored as bare dictionary form. The browser's `toGerund()` JS function appends `-ing` at render time. So a participle whose bare gloss is "see" renders as "seeing" to the user. Do NOT flag these as "missing -ing" — that's a data convention, not a bug.
- **Subjunctive / optative / imperative / infinitive bare glosses** — these intentionally show the bare dictionary form. The morph layer carries the mood signal via subscript glyphs (?, ~, !, →). Do NOT suggest "may VERB" / "let him VERB" — that was considered and rejected (it misleads English readers as permission).
- **Historical presents** — Greek narrative often uses present tense for past events. The parse correctly says `pres`. Don't suggest changing the tense.
- **Proper names** shown as bare transliterations (Παῦλος → "Paul", Ἰησοῦς → "Jesus") — that's correct behavior.
- **Indeclinables** (particles, conjunctions, prepositions) with minimal glosses like "and", "but", "to" — they're meant to be unobtrusive.
- **Word order preserving Greek placement** — the glosses are per-word, not per-sentence translations.

# Output format

Produce **markdown** with these exact section headers (omit a section if empty):

```
## High-confidence issues
- **<Greek form>** (<parse>): <problem>. Suggest: "<replacement>".

## Questionable
- **<Greek form>** (<parse>): <observation>. Less confident — context-dependent.

## Stylistic suggestions
- **<Greek form>**: <minor nit>.
```

Be precise. Use the exact Greek surface form as it appears in `txt`. Keep each bullet to one line where possible. If there are zero findings, output only: `(No findings.)`
"""


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def to_gerund(verb):
    """Mirror of the browser-side toGerund() in templates/reader.html.
    Produces what the student actually sees for a participle gloss."""
    if not verb:
        return verb
    w = verb.strip()
    if not w:
        return w
    # Auxiliary phrases
    m = re.match(r'^(am|is|are|was|were|be)\s+(.+)$', w, re.IGNORECASE)
    if m:
        return 'being ' + m.group(2)
    # Multi-word: gerund the first word only
    if ' ' in w:
        head, rest = w.split(' ', 1)
        return to_gerund(head) + ' ' + rest
    if w.endswith('ing'):
        return w
    if w.endswith('ie'):
        return w[:-2] + 'ying'
    if w.endswith('ee'):
        return w + 'ing'
    if w.endswith('e'):
        return w[:-1] + 'ing'
    vowels = sum(1 for c in w if c in 'aeiou')
    if vowels == 1 and re.search(r'[aeiou][bcdfgklmnprstvz]$', w):
        return w + w[-1] + 'ing'
    return w + 'ing'


def annotate_rendered_gloss(chapter_data):
    """Add a `_rendered` field to each entry showing what the browser displays.
    This defends against the known false-positive trap where reviewers flag
    participles without -ing because they're reading raw JSON."""
    lex = chapter_data.get('lex', {})
    for e in chapter_data.get('data', []):
        if e.get('v') or e.get('br'):
            continue
        lem = e.get('lem')
        if not lem:
            continue
        lex_entry = lex.get(lem, {})
        bare = lex_entry.get('gl')
        if not bare:
            continue
        is_ptc = e.get('prs') and re.search(r'\bptc\b', e['prs'])
        if e.get('igl'):
            e['_rendered'] = e['igl']
        elif is_ptc:
            e['_rendered'] = to_gerund(bare)
        else:
            e['_rendered'] = bare
    return chapter_data


def load_chapter(book, chapter):
    """Load and lightly normalize a chapter JSON for review."""
    path = os.path.join(_REPO_ROOT, 'build', book, f'{chapter}.json')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    # Generator writes {data: [...], lex: {...}}; tolerate either shape
    if isinstance(raw, list):
        chapter_data = {'data': raw, 'lex': {}}
    else:
        chapter_data = raw
    return annotate_rendered_gloss(chapter_data)


def resolve_targets(args):
    """Build the final (book, chapter) list from CLI args."""
    targets = []
    for s in args.chapters:
        if '/' not in s:
            print(f'ERROR: bad target "{s}" — expected <book>/<chapter>',
                  file=sys.stderr)
            sys.exit(2)
        book, ch = s.split('/', 1)
        targets.append((book, int(ch)))

    books = []
    if args.all_books:
        books = list(BOOKS.keys())
    elif args.book:
        books = list(args.book)

    rng = random.Random(args.seed)
    for book in books:
        if book not in BOOKS:
            print(f'ERROR: unknown book "{book}"', file=sys.stderr)
            sys.exit(2)
        total = BOOKS[book]['chapters']
        if args.sample and args.sample < total:
            chs = sorted(rng.sample(range(1, total + 1), args.sample))
        else:
            chs = list(range(1, total + 1))
        for ch in chs:
            targets.append((book, ch))

    # Dedupe, preserve order
    seen = set()
    out = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Review dispatch
# ═══════════════════════════════════════════════════════════════════════════
def review_one(client, model, book, chapter, out_dir):
    """Dispatch one chapter review, write the markdown, return a summary tuple."""
    chapter_data = load_chapter(book, chapter)
    book_name = BOOKS[book]['display']

    user_msg = (
        f'Review chapter: **{book_name} {chapter}**.\n\n'
        f'Chapter JSON (trimmed for review — `_rendered` shows what the student '
        f'actually sees in the browser):\n\n'
        f'```json\n{json.dumps(chapter_data, ensure_ascii=False, indent=1)}\n```'
    )

    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{
            'type': 'text',
            'text': SYSTEM_PROMPT,
            'cache_control': {'type': 'ephemeral'},
        }],
        messages=[{'role': 'user', 'content': user_msg}],
    )
    elapsed = time.time() - t0

    text_blocks = [b.text for b in resp.content if b.type == 'text']
    markdown = '\n'.join(text_blocks).strip()

    out_path = os.path.join(out_dir, f'{book}-{chapter}.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f'# Review: {book_name} {chapter}\n\n')
        f.write(f'- Model: `{model}`\n')
        f.write(f'- Input tokens: {resp.usage.input_tokens} '
                f'(cache write: {resp.usage.cache_creation_input_tokens}, '
                f'cache read: {resp.usage.cache_read_input_tokens})\n')
        f.write(f'- Output tokens: {resp.usage.output_tokens}\n')
        f.write(f'- Elapsed: {elapsed:.1f}s\n\n')
        f.write('---\n\n')
        f.write(markdown)
        f.write('\n')

    # Rough finding count — matches bullet lines under the three section headers
    finding_count = len(re.findall(r'^\s*-\s+\*\*', markdown, re.MULTILINE))
    return {
        'book': book, 'chapter': chapter,
        'elapsed': elapsed,
        'input_tokens': resp.usage.input_tokens,
        'cache_write': resp.usage.cache_creation_input_tokens,
        'cache_read': resp.usage.cache_read_input_tokens,
        'output_tokens': resp.usage.output_tokens,
        'findings': finding_count,
        'path': out_path,
    }


def write_summary(out_dir, results, model, wall):
    """Aggregate per-chapter results into _summary.md."""
    total_findings = sum(r['findings'] for r in results)
    total_in = sum(r['input_tokens'] for r in results)
    total_write = sum(r['cache_write'] for r in results)
    total_read = sum(r['cache_read'] for r in results)
    total_out = sum(r['output_tokens'] for r in results)

    lines = [
        f'# Review summary',
        '',
        f'- Model: `{model}`',
        f'- Chapters: {len(results)}',
        f'- Total findings: {total_findings}',
        f'- Wall time: {wall:.1f}s',
        f'- Tokens — input (uncached): {total_in}, '
        f'cache write: {total_write}, cache read: {total_read}, '
        f'output: {total_out}',
        '',
        '## Per-chapter',
        '',
        '| Book/Ch | Findings | In/Out tokens | Cache read | Elapsed |',
        '|---|---|---|---|---|',
    ]
    for r in sorted(results, key=lambda r: (-r['findings'], r['book'], r['chapter'])):
        lines.append(
            f'| [{r["book"]}/{r["chapter"]}]({os.path.basename(r["path"])}) '
            f'| {r["findings"]} '
            f'| {r["input_tokens"]}/{r["output_tokens"]} '
            f'| {r["cache_read"]} '
            f'| {r["elapsed"]:.1f}s |'
        )
    with open(os.path.join(out_dir, '_summary.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('chapters', nargs='*', metavar='<book/chapter>',
                    help='Target chapters, e.g. "romans/3"; repeatable')
    ap.add_argument('--book', action='append',
                    help='Include all chapters of a book (repeatable)')
    ap.add_argument('--all-books', action='store_true',
                    help='All 27 NT books (combined with --sample)')
    ap.add_argument('--sample', type=int,
                    help='Per-book: N chapters randomly sampled (deterministic '
                         'w/ --seed). Without --sample, all chapters are used.')
    ap.add_argument('--seed', type=int, default=42,
                    help='Random seed for --sample (default: 42)')
    ap.add_argument('--model', choices=list(MODELS), default='haiku',
                    help='Model tier (default: haiku)')
    ap.add_argument('--max-parallel', type=int, default=10,
                    help='Max concurrent reviewer calls (default: 10)')
    ap.add_argument('--out-dir',
                    help='Output directory (default: reviews/YYYY-MM-DD[-tag])')
    ap.add_argument('--tag', default='',
                    help='Suffix appended to the default out-dir slug')
    args = ap.parse_args()

    targets = resolve_targets(args)
    if not targets:
        ap.print_help()
        sys.exit(2)

    model_id = MODELS[args.model]

    if args.out_dir:
        out_dir = args.out_dir
    else:
        today = dt.date.today().isoformat()
        slug = f'{today}-{args.tag}' if args.tag else today
        out_dir = os.path.join(_REPO_ROOT, 'reviews', slug)
    os.makedirs(out_dir, exist_ok=True)

    print(f'Model: {model_id}', file=sys.stderr)
    print(f'Targets: {len(targets)} chapter(s)', file=sys.stderr)
    print(f'Output: {out_dir}', file=sys.stderr)
    print(f'Max parallel: {args.max_parallel}', file=sys.stderr)
    print('', file=sys.stderr)

    client = anthropic.Anthropic()

    tg = time.time()
    results = []
    errors = []
    with cf.ThreadPoolExecutor(max_workers=args.max_parallel) as ex:
        futs = {
            ex.submit(review_one, client, model_id, book, ch, out_dir): (book, ch)
            for book, ch in targets
        }
        for i, fut in enumerate(cf.as_completed(futs), 1):
            book, ch = futs[fut]
            try:
                r = fut.result()
                results.append(r)
                print(f'  [{i}/{len(targets)}] {book}/{ch}  '
                      f'findings={r["findings"]}  '
                      f'cache_read={r["cache_read"]}  '
                      f'{r["elapsed"]:.1f}s', file=sys.stderr)
            except Exception as e:
                errors.append((book, ch, str(e)))
                print(f'  [{i}/{len(targets)}] {book}/{ch}  FAILED: {e}',
                      file=sys.stderr)

    wall = time.time() - tg
    if results:
        write_summary(out_dir, results, model_id, wall)
    print(f'\nDone: {len(results)}/{len(targets)} reviews in {wall:.1f}s',
          file=sys.stderr)
    if errors:
        print(f'Errors: {len(errors)}', file=sys.stderr)
        for book, ch, err in errors[:5]:
            print(f'  {book}/{ch}: {err}', file=sys.stderr)
    print(f'Summary: {os.path.join(out_dir, "_summary.md")}', file=sys.stderr)
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
