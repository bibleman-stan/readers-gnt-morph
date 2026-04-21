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

The overseer retired 2026-04-20; Stan is the sole authority. Session bookends produce artifacts in a per-session folder that survives compaction. Shape matches sibling repos (`readers-gnt`, `readers-bofm`) with morph-specific adjustments (sense-line drift awareness; HANDOFF.md as triggered-consult rather than every-wake mandatory).

### Session folder convention

Each Claude Code session (JSONL boundary) gets its own folder:

`private/03-sessions/yyyy-mm-dd-brief_description/`

Use the **session start date**. A compaction-wake starts a new session; create a new folder with a new descriptor even if the calendar date matches a pre-compaction folder. Multiple folders sharing a date with different descriptors is correct and expected.

The folder is the persistent write surface for the session. Session memory evaporates at compaction; the folder survives.

### CHECK-IN at session start

**MANDATORY (read every wake, including short "hey wake up" signals):**
1. **This CLAUDE.md in full** — active rules may have changed
2. **Most recent `private/03-sessions/yyyy-mm-dd-*/session-notes.md`** — prior-session carry-forwards, discipline patterns, open threads
3. **`git log --oneline -10`** — any unfamiliar commit is a state change to understand before working
4. **`PYTHONIOENCODING=utf-8 python src/sync_senselines.py`** (report-only) — morph-specific: sense-line drift check against the `readers-gnt` substrate. **If drift exists, default to `--regen` without asking** — observed drift in a substrate-consumer pipeline IS the instruction to sync.

**CONSULT-ON-TRIGGER (evaluate the trigger; a silent skip is a check-in failure):**
- [HANDOFF.md](HANDOFF.md) — **trigger:** architectural question, first wake on a new machine, or anything that might intersect the eight lessons / channel architecture / validator discipline. **Skip when:** routine execution work (regens, gloss overrides, nav UI) with no architectural implication.
- [NOTICE.md](NOTICE.md) — **trigger:** touching vendored data or making licensing-relevant changes. **Skip when:** code / pipeline / UX work with no vendored-corpus touching.
- Validator (`PYTHONIOENCODING=utf-8 python src/validate_chapter.py build/acts/9.json`) — **trigger:** morpheus.py / inflect_gloss.py / generator touched since last verified run. **Skip when:** recent clean run + no pipeline code changes.
- `private/open-items.md` — **trigger:** choosing what to work on next, or at wrap-up to update. **Skip when:** Stan has already named today's focus.
- `C:\vaults-nano\my_brain\00_Inbox\claude-brainstorming.md` — **trigger:** Stan's wake signal references a mobile-captured idea, or you want to check the inbox for morph-scope items. **Skip when:** focus is already explicit and no inbox reference made.

**SELF-REPORT before first substantive response** — one line per mandatory file (e.g., `- CLAUDE.md: read`), plus read/skip + trigger evaluation for each consult-on-trigger item that fired. A silent skip is a check-in failure.

### During the session

Log as things happen — in the session folder's `session-notes.md` (draft as you go, or assemble at wrap):
- **Discipline failures** Stan catches. If ≥2 share a common underlying mode (over-structuring, alignment-skip, imposing-vs-revealing, pattern-matching-over-diagnostic, rule-multiplication, present-observation-as-choice-point), name the mode explicitly.
- **Withdrawn or discarded proposals** — with the reason (anti-over-claim discipline).
- **Workflow use-count** running tally — agent dispatches, commits, memory changes, regen runs. Recurring use is validation of the workflow.

### WRAP-UP at session end

When Stan signals "wrap it up" (or equivalent), produce in the session folder:

1. **`full-transcript.md`** — verbatim dialogue extracted from the session JSONL. Dispatch a Sonnet agent with the JSONL path (`C:\Users\bibleman\.claude\projects\c--Users-bibleman-repos-readers-gnt-morph\<session-id>.jsonl`, most recent by mtime if uncertain) to stream-process: numbered turns alternating Stan / Claude, strip `tool_use` and `tool_result` blocks, strip `<system-reminder>` blocks. Keep everything else verbatim.
2. **`session-notes.md`** — session arc, commits landed, discipline observations with common-mode grouping, withdrawn proposals, workflow use-count, carry-forwards for the next session. Preserve load-bearing Stan phrases verbatim.
3. **`dialogue-notes.md`** — produce only for methodology-heavy sessions where the dialogue arc itself is the work (not just executing a pre-specified task). Captures the reasoning path. Most morph sessions are execution; this file is rare here.
4. **Update `private/open-items.md`** — mark applied items with commit hash + date; add new items surfaced this session; prune when items land.
5. **Update [HANDOFF.md](HANDOFF.md)** — ONLY for architectural-retrospective additions (trajectory, lessons learned, resumption-checklist changes). Per-session run-downs belong in session notes, not HANDOFF.
6. **Wrap-up message** to Stan (4-8 lines): commits landing, files touched, items closed, items opened, session-folder path, anything to flag.
7. **Commit.**

### Context-threshold discipline

- **Green zone (0-60%):** execute normally.
- **Yellow zone (60-80%):** start drafting `session-notes.md` in the session folder; consider wrapping at natural breakpoints. Write out anything that only lives in memory.
- **Red zone (80%+):** stop new execution, wrap up. The runway between 80% and auto-compact is the margin for wrap-up itself.

When in doubt, write it down. Files survive compaction; working memory does not.

### Compaction-resume protocol

Compaction is a session boundary. When resuming from a compaction summary, execute the full CHECK-IN protocol above and create a new session folder with a new descriptor. A compaction-wake gives context but does not exercise the orientation muscles — silent skip is a check-in failure. Short-form wake signals ("hey wake up") still require the full mandatory reads; mandatory is short enough that skipping saves no meaningful time.

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
