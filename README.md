# Reader's GNT — Morpheme Reader

A browser-based reading tool that renders the Greek New Testament with layered, student-toggleable visual annotations of its morphology — augments, tense formatives, case suffixes, participle markers, voice outlines, tense glyphs, mood subscripts, gender coloring, and frequency-banded glosses.

The goal: let students **see** morphological structure rather than decode abbreviations.

**Status:** Full book of Acts published (28 chapters, 18,412 words, 99.5%+ validated correctness).

## What it looks like

Open `index.html` locally for a landing page linking all 28 chapters, or browse any `acts<N>_reader.html` standalone. Each chapter has a toolbar with 10 toggleable visual layers plus All/Bare master buttons and a `?` help modal with a full legend. Click any word for a parsing panel.

See `about.html` for the full pitch — written for both students and researchers/teachers.

## How it works

This is an analytical layer built on top of a separate colometric reading edition. The pipeline:

```
MorphGNT (morphologically-tagged GNT)
      ↓
generate_chapter.py → merges stem data, glosses, NT frequencies, and sense-lines
      ↓
acts<N>_data.json (structured morpheme decomposition per word)
      ↓
validate_chapter.py → quality gate; ~11 structural checks
      ↓
build_html.py → injects JSON into template.html
      ↓
acts<N>_reader.html (standalone, client-side rendering)
```

## Architectural core

`morpheus.py` is the decomposition engine — pure Python, no external deps. It uses an **overlap-capable channel architecture** where each visual channel (morpheme / participle / case / gender / voice) stores its own span list, and segmentation takes the union of all channel boundaries. This lets σα in νηστεύσαντες function simultaneously as an aorist formative AND as the start of the participle marker, without forcing a linear decomposition that would falsify the morphology.

## Relationship to the Reader's GNT

This project consumes sense-line data from the [Reader's GNT](https://github.com/bibleman-stan/readers-gnt) as read-only input. It never modifies the substrate. If the Reader's GNT evolves its line breaks, this project rebuilds on the new substrate without changes.

## Getting started

**Requirements:** Python 3 with `pyyaml`.

**Install:**
```bash
pip install pyyaml
```

**Regenerate a chapter:**
```bash
python generate_chapter.py 9 > acts9_data.json
python validate_chapter.py acts9_data.json
python build_html.py acts9_data.json template.html acts9_reader.html
```

(Note: `generate_chapter.py` reads sense-lines from `c:/Users/bibleman/repos/readers-gnt/data/text-files/v4-editorial/`. Edit the `SENSE_LINES_DIR` constant at the top of the file to point at your local clone of the sibling project.)

## Documentation

- **[HANDOFF.md](HANDOFF.md)** — the full architecture + retrospective + lessons learned. This is the primary developer document. Read Parts 0, 1.5, 2, 3 first; Parts 4 and 5 are the accumulated wisdom.
- **[NOTICE.md](NOTICE.md)** — attribution for the vendored academic data corpora.
- **[CLAUDE.md](CLAUDE.md)** — orientation document for AI collaborators (Claude Code sessions) working in this repo.

## License

MIT (see [LICENSE](LICENSE)). Vendored data retains its original licenses (see NOTICE.md).
