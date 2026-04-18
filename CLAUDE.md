# readers-gnt-morph — Claude Code Instructions

Read this file completely before doing anything in this repo. It is your orientation document for every session.

---

## What This Project Is

A browser-based morpheme reader for the Greek New Testament. Each Greek word is decomposed into its morphological pieces (preposition prefix → augment → stem → formative → ending), with color-coded visual annotations that students can toggle on/off layer-by-layer. The goal: let students **see** Greek morphology rather than decode abbreviations mentally.

**Status:** Full book of Acts published (28 chapters, 99.5%+ validated correctness). Pipeline is book-agnostic as of 2026-04-17 (Bundle 3 refactor): `src/books.py` registry, `--book` arg on `generate_chapter.py`, `src/audit_coverage.py` pre-generation gate. Other books being generated as schedule allows.

- **Repo:** github.com/bibleman-stan/readers-gnt-morph (public)
- **Deploy:** live at `morph.gnt-reader.com` (GitHub Pages, `docs/` folder).
- **User:** Stan (thebibleman77@gmail.com)

---

## Read These Files FIRST (in order)

Before any substantive work:

1. **This CLAUDE.md in full** — you're doing this now.
2. **[HANDOFF.md](HANDOFF.md)** — the complete project retrospective with architecture, trajectory, eight lessons learned, and a **Resumption Checklist in Part 6.5** written specifically for a future Claude waking up into this project. Read Parts 0, 1.5, 2, 3 closely; Parts 4, 5, 6 are accumulated wisdom.
3. **[NOTICE.md](NOTICE.md)** — vendored data attribution. Know where the academic corpora come from and what licenses govern them.
4. **Run the validator** (see workflow below) on any recent chapter to confirm the pipeline still works on your machine.

---

## Your Cubicle — What You Own, What You Don't

This is the **morph analytical layer**. You are part of a family of projects; understanding your cubicle boundary is essential.

**You own (full read/write authority):**
- Everything in `readers-gnt-morph/` — code, templates, HTML outputs, chapter JSONs, vendored data, documentation

**You do NOT touch:**
- **`c:/Users/bibleman/repos/readers-gnt/`** — the sibling reading edition. Your `generate_chapter.py` reads sense-lines from it, but you NEVER write to it. Editorial decisions about line breaks happen in a different Claude session working in that repo. If you see a problem with a sense-line, SURFACE IT TO STAN — do not edit it yourself.
- **`c:/Users/bibleman/repos/readers-bofm/`** — a parallel colometric project in the same family. Not your concern.
- **`c:/Users/bibleman/repos/overseer-workspace/`** — the overseer's cross-project workspace. You can READ it if useful for context; you do not write to it.

**The "substrate as stable API" principle:** the sense-line files at `readers-gnt/data/text-files/v4-editorial/` are the interface contract between the sibling project and you. Your job is to CONSUME them cleanly. Their format (verse markers, one line per sense-line, UTF-8 polytonic Greek, blank lines between verses) does not change shape. If you think you need structural enrichment in the substrate, fork the idea into a different project — do not propose modifying the substrate.

---

## The Validator Is the Quality Gate

**This is the single most important thing about this project.** `validate_chapter.py` is an automated structural auditor that knows what "correct" looks like across 11 categories (augment extraction, formative identification, participle markers, case suffixes, compound-verb prefix detection, etc.). It uses the stem database to skip legitimate false positives (liquid aorists, indeclinable names, suppletive verbs).

**Before any substantive change to `morpheus.py`, run the validator on the five stress-test chapters:** Acts 1, 9, 13, 17, 26. These were chosen for genre variety (narrative, conversion, sermon, philosophical, defense speech) and cover most edge cases. If a change breaks coverage on any of them, fix or revert before proceeding.

**Do NOT let the validator coverage regress.** The project is currently at 99.5%+ across all 28 chapters (~100 flagged edge cases, all documented in HANDOFF.md Part 6). That number is hard-won — it represents ten systemic morpheus.py fixes driven by validator findings. Regression destroys that.

---

## Standard Workflows

### Generate a new chapter (different book, e.g. Romans)

Repo layout (run all commands from repo root):
- `src/` — pipeline scripts (morpheus.py, generate_chapter.py, build_html.py, validate_chapter.py)
- `templates/reader.html` — master HTML template (was `template.html` pre-2026-04-17)
- `data/` — vendored corpora (MorphGNT, greek-inflexion, morphological-lexicon)
- `build/<book>/<N>.json` — intermediate per-chapter decomposition data
- `docs/` — the deployable site (GitHub Pages serves this folder)
  - `docs/index.html` — site-level book picker
  - `docs/about.html` — user-facing explainer
  - `docs/CNAME` — custom domain pointer (`morph.gnt-reader.com`)
  - `docs/<book>/index.html` — per-book chapter grid
  - `docs/<book>/<N>.html` — chapter readers

```bash
# 1. Verify the book is in the registry (src/books.py). If not, add it
#    with display name, MorphGNT file, chapter count, canonical order,
#    and sense_code (readers-gnt substrate directory key).

# 2. Audit verb-stem coverage before committing to generate.
#    Fails with list of missing lemmas if below 90%.
PYTHONIOENCODING=utf-8 python src/audit_coverage.py <book-code>
# e.g. python src/audit_coverage.py romans

# 3. Bulk-generate + build (one book, one command, ~5 seconds per book).
#    This is the in-process orchestrator — loads stems/lex/freq ONCE
#    and iterates all chapters. DO NOT use generate_chapter.py in a
#    loop across chapters: each invocation re-parses ~2MB of YAML,
#    which is the dominant cost at scale (was 400s for full-GNT;
#    bulk_generate does the whole GNT in 23s).
PYTHONIOENCODING=utf-8 python src/bulk_generate.py <book-code>
# Multiple books: PYTHONIOENCODING=utf-8 python src/bulk_generate.py acts romans
# Whole GNT:      PYTHONIOENCODING=utf-8 python src/bulk_generate.py

# 4. Validate morphology (pick representative chapter(s)).
PYTHONIOENCODING=utf-8 python src/validate_chapter.py build/<book-code>/<N>.json

# 5. Validate glosses (anti-pattern scan + ground-truth test set).
PYTHONIOENCODING=utf-8 python src/validate_glosses.py --testset
PYTHONIOENCODING=utf-8 python src/validate_glosses.py build/<book-code>/<N>.json

# Single-chapter generation (debugging / reproducing a specific case)
# still works via the per-chapter CLI:
PYTHONIOENCODING=utf-8 python src/generate_chapter.py <N> --book <book-code> \
    > build/<book-code>/<N>.json
python src/build_html.py build/<book-code>/<N>.json templates/reader.html \
    docs/<book-code>/<N>.html
```

Expect 2-5 new edge-case categories when you run on Romans (dense argumentation), Hebrews (unusual perfects), or Revelation (apocalyptic lexicon, proper names). All should be fixable via the same methodology used for Acts — extend `morpheus.py` rules, re-run validator, ensure no regressions on Acts.

### Fix a bug the validator found

1. Reproduce in a REPL from `src/`: `import morpheus; morpheus.decompose_verb(<wd>, <stems_db>, ...)`
2. Fix the rule in `src/morpheus.py` — usually a table entry or a new pattern.
3. Re-run validator on all five stress-test chapters (`build/acts/{1,9,13,17,26}.json`) to check regressions.
4. Only then regenerate and rebuild.

### Add a new visual layer

See HANDOFF.md Part 4 Lesson 4 — each visual channel should occupy a different CSS dimension (text color, background, underline, border, glyph, subscript) so they never collide. New layer checklist:
1. Identify what CSS property/spatial zone isn't used yet.
2. Add CSS rule gated by `.L-<newlayer>` on `#reader`.
3. Add toggle function + toolbar button.
4. Extend the renderer to emit the necessary classes.
5. Update the legend modal (`?` button content) AND about.html.
6. Regenerate all affected chapters.

---

## Accumulated Feedback & Standing Discipline

Two feedback memories from prior sessions in this project (they live in the user-side memory folder, but the principles are summarized here so you don't miss them):

### Validate data before debugging display
Before chasing any display bug, audit the data. Frequency miscalculations, missing stem entries, incomplete corpus downloads — all manifest as "weird display problems" that waste hours. Dispatch a subagent to sanity-check data quality BEFORE touching CSS.

The origin: the project spent an hour debugging gloss CSS on short words like ἔτι. The real problem was that NT frequencies were computed from Acts alone (1 book) instead of the full NT (27 books). ἔτι showed as rare when it's actually common. Fixing the data eliminated the display problem entirely.

### Deliberate implementation — think through dependencies BEFORE coding
Before any non-trivial feature or bug fix, dispatch a pre-flight subagent to enumerate failure modes across (a) data quality, (b) content edge cases, (c) visual interactions, (d) CSS dependencies, (e) browser behavior. Address them in the plan. Only then code.

The origin: reactive fix-break cycles were eating time. Every feature revealed 2-3 dependencies that should have been caught before coding. The pre-flight audit pattern reduces this from "hours of cascading fixes" to "5 minutes of planning."

---

## Session bookend protocol

Canonical shared source: [`overseer-workspace/SESSION-BOOKEND-PROTOCOL.md`](../overseer-workspace/SESSION-BOOKEND-PROTOCOL.md) — CHECK-IN, WRAP-UP, context thresholds, and compaction-resume protocol. **Read it at the start of every session.**

### morph-specific CHECK-IN file list (structured as mandatory + consult-on-trigger per shared protocol)

**MANDATORY (read every wake — including short "hey wake up" signals):**
1. This CLAUDE.md in full
2. `private/OVERSEER-DIRECTIONS.md` active-directives section (NOT the archive if/when one exists) — created 2026-04-19; carries cross-project push-FROM-HERE items + active open items + sync log
3. [HANDOFF.md](HANDOFF.md) — architectural retrospective; Resumption Checklist in Part 6.5 is the most load-bearing section on a fresh wake
4. `C:\vaults-nano\my_brain\00_Inbox\claude-brainstorming.md` — scope per shared protocol (morph items only)
5. `git log --oneline -10`

**CONSULT-ON-TRIGGER (evaluate the trigger; do NOT silently skip):**
- [NOTICE.md](NOTICE.md) — **trigger:** touching vendored data or making licensing-relevant changes. **Skip when:** code / pipeline / UX / deployment work not touching vendored corpora.
- Run the validator (`PYTHONIOENCODING=utf-8 python src/validate_chapter.py build/acts/9.json`) — **trigger:** first wake on a new machine, OR you suspect pipeline state has shifted. **Skip when:** recent validator run in the session log shows clean state.
- `c:/Users/bibleman/repos/overseer-workspace/LANDSCAPE-MAP.md` — **trigger:** cross-project state matters to today's task (e.g., readers-gnt substrate change, shared-methodology discussion). **Skip when:** morph-local work with no cross-project implications.

**Self-report is mandatory before your first substantive response** — see the shared protocol's SELF-REPORT section for the one-line-per-file format. A silent skip is a check-in failure.

### morph-specific WRAP-UP additions

Session notes go to `private/03-sessions/[YYYY-MM-DD]-[topic-slug]/session-notes.md`. The "What the notes should contain" bullet list from the shared protocol applies in full. HANDOFF.md updates ONLY for architectural retrospective additions (trajectory, lessons learned, resumption-checklist), not per-session run-downs.

### Context-threshold and compaction-resume — see shared protocol

Threshold discipline and compaction-resume rules live in the shared protocol (revised 2026-04-19 so execution-heavy sessions like full-GNT regens or horde dispatches aren't interrupted at 40%).

---

## Agent Dispatch — Match Model to Task

When dispatching subagents via the Agent tool:

- **Haiku** (cheapest, fastest): file moves, glob/ls formatting, mechanical reference lookups, yes/no checks against file content.
- **Sonnet** (mid-tier): scanner runs with defined rules, quick consistency checks, documentation updates following a template, short adversarial checks on a single specific question, cross-project consistency checks once both sides are stable.
- **Opus** (reasoning-heavy): multi-angle adversarial audits, methodology synthesis, restructuring major documents, novel rule design, anything where the judgment IS the work product.

**When in doubt, Sonnet is the right default.** Stan shouldn't have to think about this — you make the call.

---

## The Don't-Do List

From HANDOFF.md Part 6.5, carried forward because these will cost you hours if you try again:

- **Don't try to make overlapping morphemes into linear spans.** The channel architecture exists because this is impossible. If tempted, re-read HANDOFF.md Part 3.
- **Don't fix the gloss positioning on 2-3 char words beyond the current state.** Accepted as a known limitation. You will burn hours.
- **Don't re-add the discourse markers layer without discussing with Stan first** — it was explicitly removed.
- **Don't remove the `All`/`Bare`/`?` buttons** — user-facing UX.
- **Don't build new features without updating the legend modal + about.html** to document them.
- **Don't modify `morpheus.py` without re-running the validator on all five stress-test chapters afterward.**
- **Don't propose modifying the readers-gnt substrate to make your life easier.** See the cubicle boundary above.

---

## What Stan Does / What Claude Does

**Stan:**
- Decides what gets built next (feature priorities, v2 candidates)
- Reviews all substantive changes before they land
- Pushes to GitHub
- Has final say on pedagogical decisions (what helps students, what overwhelms them)

**Claude:**
- Implements within the scope above
- Runs the validator before and after every morpheus.py change
- Writes thoughtful commit messages
- Writes session notes to `private/03-sessions/` when substantive changes land; updates HANDOFF.md only for architectural retrospective additions
- Surfaces edge cases and tradeoffs to Stan rather than making them silently
- Stays in the cubicle — does not edit readers-gnt or readers-bofm

---

## Future Roadmap

See HANDOFF.md Part 6 for ranked next-move ideas — click-to-reveal mode, focus mode, hover-to-preview, mastery-based color fade, SRS integration, parse quiz mode, proficiency presets. Ordered by research-backed likely value.

Beyond Acts: the pipeline is book-agnostic. Romans and Hebrews are natural next targets (different lexical/syntactic profiles will stress-test the validator further). Eventually: full GNT.

A Hebrew equivalent is on the long-horizon roadmap. See HANDOFF.md Part 5 for detailed guidance on porting this approach to the Tanakh.
