# Reader's GNT — Morpheme Reader

A browser-based reading tool that renders the Greek New Testament with layered, student-toggleable visual annotations of its morphology — augments, tense formatives, case suffixes, participle markers, voice outlines, tense glyphs, mood subscripts, gender coloring, and frequency-banded glosses.

The goal: let students **see** morphological structure rather than decode abbreviations.

**Status:** Full Greek New Testament published — all 27 books, 260 chapters. Morphological decomposition validated at 99.5%+ across the corpus by the automated `validate_chapter.py` quality gate; English glosses validated by a ground-truth test set + anti-pattern scan.

## Live at [morph.gnt-reader.com](https://morph.gnt-reader.com)

Pick any book from the landing page, then a chapter. Each chapter has a toolbar with toggleable morphology layers, case sub-toggles, gloss frequency bands, and participle/tense/voice/mood overlays, plus `All`/`Bare` master buttons and a `?` help modal with a full legend. Click any word for a full parsing panel. Navigate chapters with the ←/→ arrows (desktop), swipe (mobile), or the book+chapter title in the toolbar (opens a full nav panel down to the verse level).

Your toolbar selections and font size persist across chapters via `localStorage`.

See [about.html](https://morph.gnt-reader.com/about.html) for the full pitch — written for both students and researchers/teachers.

## How it works

This is an analytical layer built on top of a separate colometric reading edition ([Reader's GNT](https://github.com/bibleman-stan/readers-gnt)). Sense-line breaks come from that sibling; morphological decomposition is this project's own work. The pipeline:

```
MorphGNT (morphologically-tagged GNT)
      ↓
src/bulk_generate.py → merges stem data, glosses, NT frequencies, and sense-lines
                       (loads stems/lex/freq once; iterates all 260 chapters in ~23s)
      ↓
build/<book>/<N>.json (structured morpheme decomposition per word, per chapter)
      ↓
src/validate_chapter.py → quality gate; ~11 structural checks
      ↓
src/build_html.py → injects JSON into templates/reader.html
      ↓
docs/<book>/<N>.html (standalone, client-side rendering; GitHub Pages serves docs/)
```

## Architectural core

`src/morpheus.py` is the decomposition engine — pure Python, no external deps. It uses an **overlap-capable channel architecture** where each visual channel (morpheme / participle / case / gender / voice) stores its own span list, and segmentation takes the union of all channel boundaries. This lets σα in νηστεύσαντες function simultaneously as an aorist formative AND as the start of the participle marker, without forcing a linear decomposition that would falsify the morphology.

`src/inflect_gloss.py` handles English-gloss inflection for indicative verbs (ἐξελέξατο → "chose", ἀνελήμφθη → "was taken up"), so the gloss reads like the verb-in-context rather than the dictionary lemma.

## Relationship to the Reader's GNT substrate

Sense-line data at `readers-gnt/data/text-files/v4-editorial/<NN>-<book>/<book>-<NN>.txt` is consumed **read-only**. When the Reader's GNT evolves its line breaks (editorial refinements, canon updates, methodology sweeps), `src/sync_senselines.py` detects the drift via SHA-256 manifest comparison and regenerates the affected chapters on demand — typically a few seconds per book.

## Getting started

**Requirements:** Python 3.10+ with `pyyaml`.

**Install:**
```bash
pip install pyyaml
```

**Regenerate + rebuild the whole corpus** (fastest path — the default):
```bash
PYTHONIOENCODING=utf-8 python src/bulk_generate.py
```

**Regenerate a single book:**
```bash
PYTHONIOENCODING=utf-8 python src/bulk_generate.py romans
```

**Regenerate a single chapter** (debugging path):
```bash
PYTHONIOENCODING=utf-8 python src/generate_chapter.py 9 --book acts > build/acts/9.json
python src/build_html.py build/acts/9.json templates/reader.html docs/acts/9.html
```

**Validate morphology:**
```bash
PYTHONIOENCODING=utf-8 python src/validate_chapter.py build/acts/9.json
```

**Validate English glosses:**
```bash
PYTHONIOENCODING=utf-8 python src/validate_glosses.py --testset
PYTHONIOENCODING=utf-8 python src/validate_glosses.py build/acts/9.json
```

**Audit verb-stem coverage before adding a new book:**
```bash
PYTHONIOENCODING=utf-8 python src/audit_coverage.py romans   # or --all
```

**Sync sense-line changes from the Reader's GNT substrate:**
```bash
PYTHONIOENCODING=utf-8 python src/sync_senselines.py           # report only
PYTHONIOENCODING=utf-8 python src/sync_senselines.py --regen   # regen + rebuild stale chapters
```

The sense-line path defaults to `C:/Users/bibleman/repos/readers-gnt/data/text-files/v4-editorial`. Override with the `SENSE_LINES_DIR` environment variable.

## Documentation

- **[HANDOFF.md](HANDOFF.md)** — full architecture + retrospective + lessons learned. Primary developer document. Read Parts 0, 1.5, 2, 3 first; Parts 4–6 are accumulated wisdom + the Resumption Checklist for waking into the project cold.
- **[NOTICE.md](NOTICE.md)** — attribution for the vendored academic data corpora (MorphGNT SBLGNT, James Tauber's greek-inflexion, morphological-lexicon).
- **[CLAUDE.md](CLAUDE.md)** — orientation document for Claude Code sessions working in this repo. Includes the session bookend protocol.

## License

MIT (see [LICENSE](LICENSE)). Vendored data retains its original licenses (see [NOTICE.md](NOTICE.md)).
