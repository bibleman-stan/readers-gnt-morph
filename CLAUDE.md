# readers-gnt-morph — Claude Code Instructions

Read this file completely before doing anything in this repo. It is your orientation document for every session.

---

## What This Project Is

A browser-based morpheme reader for the Greek New Testament. Each Greek word is decomposed into its morphological pieces (preposition prefix → augment → stem → formative → ending), with color-coded visual annotations that students can toggle on/off layer-by-layer. The goal: let students **see** Greek morphology rather than decode abbreviations mentally.

**Status:** Full Greek New Testament published — all 27 books, 260 chapters, live at morph.gnt-reader.com. Morphological decomposition validated at 99.5%+ corpus-wide by `src/validate_chapter.py`; English glosses validated by `src/validate_glosses.py` (ground-truth test set + anti-pattern scan). Pipeline is book-agnostic: `src/books.py` registry, `--book` arg on `generate_chapter.py`, `src/bulk_generate.py` whole-GNT regen in ~23s, `src/audit_coverage.py` pre-generation gate.

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

**You do NOT touch (read-only at most):**
- **`c:/Users/bibleman/repos/readers-gnt/`** — the sibling reading edition; morph's substrate source. Your `generate_chapter.py` reads sense-lines from it, but you NEVER write to it. Editorial decisions about line breaks happen in a different Claude session working in that repo. If you see a problem with a sense-line, SURFACE IT TO STAN — do not edit it yourself.
- **`c:/Users/bibleman/repos/readers-bofm/`** — Book of Mormon colometric edition (the proof-of-concept reference impl). Not your concern.
- **`c:/Users/bibleman/repos/readers-tanakh/`** — Hebrew Bible colometric edition. Not your concern.
- **`c:/Users/bibleman/repos/rev-reader/`** — Revelation annotation apparatus (another GNT-substrate consumer, parallel to you). Not your concern.
- **`c:/Users/bibleman/repos/atu-method/`** — the shared ATU-method (Atomic Thought Unit) methodology + Python infrastructure repo, extracted 2026-04-26 from the colometric proof-of-concepts. The colometric editions import its package; **morph does not** — morph consumes the substrate *output* (sense-line files), not the colometry tooling. Read it for FYSA context if useful; never write to it.

**The "substrate as stable API" principle:** the sense-line files at `readers-gnt/data/text-files/v4/grk/` are the interface contract between the sibling project and you. Your job is to CONSUME them cleanly. Their *format* (verse markers, one line per sense-line, UTF-8 polytonic Greek, blank lines between verses) is stable — but the *path* can move (it was `v4-editorial/` until the 2026-04-26 ATU-method restructure split it into `v4/grk/` + `v4/eng-kjv/`). If the path moves again, `sync_senselines.py` will error loudly; fix `SENSE_LINES_DIR` in `generate_chapter.py` + `_SENSE_DIR` in `sync_senselines.py` + the `books.py` docstring. If you think you need structural enrichment in the substrate, fork the idea into a different project — do not propose modifying the substrate.

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

## Orientation & continuity

The overseer retired 2026-04-20; Stan is the sole authority. **Sessionizing is retired (2026-05-14)** — no per-session folders, no `session-notes.md` / `full-transcript.md` / `dialogue-notes.md` / `proposals-for-stan.md`, no WRAP-UP ceremony. The Claude Code JSONL at `C:\Users\bibleman\.claude\projects\c--Users-bibleman-repos-readers-gnt-morph\<session-id>.jsonl` is the verbatim record — it already captures every turn losslessly, so re-transcribing it into folder artifacts was redundant work. Surface state inline in chat; persist durable work-queue items in `private/open-items.md`; that's it.

The existing `private/03-sessions/` folders are frozen historical artifacts from the sessionized era — don't add to them, don't delete them.

### CHECK-IN at session start

**MANDATORY (read every wake, including short "hey wake up" signals):**
1. **This CLAUDE.md in full** — active rules may have changed
2. **`private/open-items.md`** — the rolling work queue; prior-session carry-forwards live here now
3. **`git log --oneline -10`** — any unfamiliar commit is a state change to understand before working
4. **Sense-line sync against the `readers-gnt` substrate.** This is morph's most important operational rule because morph's whole job is to render that substrate accurately. The standing action sequence on every wake — no exceptions, no permission step:
   1. Run `PYTHONIOENCODING=utf-8 python src/sync_senselines.py` (report mode).
   2. **If even one chapter is stale, immediately run `python src/sync_senselines.py --regen`.** Do not ask. Do not pause to "confirm with Stan." Observed drift in a substrate-consumer pipeline IS the directive to sync — Stan's editorial work in `readers-gnt` is the instruction; my job is to absorb it.
   3. **Commit the regen** — `git add build/ docs/ && git commit -m "Sync sense-line changes from readers-gnt — N chapters"`.
   4. Self-report the chapter count + commit hash in the check-in message.

   If `report` says "All in sync. No chapters stale." — note that explicitly in the self-report. Do not skip step 1 even when expecting clean state; the whole point is verification, not assumption. Substrate path is `readers-gnt/data/text-files/v4/grk/` (was `v4-editorial/` before the 2026-04-26 ATU-method restructure).

**CONSULT-ON-TRIGGER (evaluate the trigger; a silent skip is a check-in failure):**
- [HANDOFF.md](HANDOFF.md) — **trigger:** architectural question, first wake on a new machine, or anything that might intersect the eight lessons / channel architecture / validator discipline. **Skip when:** routine execution work (regens, gloss overrides, nav UI) with no architectural implication.
- [NOTICE.md](NOTICE.md) — **trigger:** touching vendored data or making licensing-relevant changes. **Skip when:** code / pipeline / UX work with no vendored-corpus touching.
- Validator (`PYTHONIOENCODING=utf-8 python src/validate_chapter.py build/acts/9.json`) — **trigger:** morpheus.py / inflect_gloss.py / generator touched since last verified run. **Skip when:** recent clean run + no pipeline code changes.
- `C:\vaults-nano\my_brain\00_Inbox\claude-brainstorming.md` — **trigger:** Stan's wake signal references a mobile-captured idea, or you want to check the inbox for morph-scope items. **Skip when:** focus is already explicit and no inbox reference made.

**SELF-REPORT before first substantive response** — one line per mandatory file (e.g., `- CLAUDE.md: read`), plus read/skip + trigger evaluation for each consult-on-trigger item that fired. A silent skip is a check-in failure.

### Post-compaction JSONL re-acquisition (MANDATORY)

When the wake follows a compaction event (a system summary is present and the JSONL is significantly longer than the visible conversation), the FIRST action after the orientation reads is to read **the last 20-30 user↔assistant turns** from the JSONL verbatim. The compaction summary preserves structural narrative but loses verbatim turn-by-turn detail — Stan's exact phrasing, his minor corrections, the tradeoffs he weighed. "Kind of" memory from the summary alone lets me bluff continuity but fails the actual trust state. Read the recent window proactively; don't grep-on-demand only when challenged. Report the re-read in the self-report.

### During the session

- **Surface state inline.** Discipline failures Stan catches, withdrawn proposals, decisions made — say them in chat as they happen. Don't defer to a wrap artifact; there is no wrap artifact.
- **Commit proactively.** The JSONL survives compaction but the working tree doesn't get auto-saved — commit substantive work as it lands so a compaction never costs uncommitted changes. Status claims come AFTER the commit.
- **`private/open-items.md` is the only durable write surface.** When a work-queue item is surfaced, deferred, or completed, update `open-items.md` — mark applied items with commit hash + date, add new items, prune landed ones. This is the one file that has to survive across sessions.
- **[HANDOFF.md](HANDOFF.md)** — update ONLY for architectural-retrospective additions (trajectory, lessons learned, resumption-checklist changes). Not a per-session log.

### WRAP-UP

There is no wrap ceremony. When Stan signals "wrap it up": make sure substantive work is committed and pushed, make sure `private/open-items.md` reflects reality, give a 2-4 line summary inline (commits landed, items closed/opened, anything to flag), and stop. Do NOT generate transcript dumps or session-notes files — the JSONL is the record.

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
- Keeps `private/open-items.md` current; updates HANDOFF.md only for architectural retrospective additions (no session notes — the JSONL is the record)
- Surfaces edge cases and tradeoffs to Stan inline, as they happen, rather than making them silently or deferring to a wrap artifact
- Stays in the cubicle — does not edit readers-gnt, readers-bofm, readers-tanakh, rev-reader, or atu-method

---

## Future Roadmap

See HANDOFF.md Part 6 for ranked next-move ideas — click-to-reveal mode, focus mode, hover-to-preview, mastery-based color fade, SRS integration, parse quiz mode, proficiency presets. Ordered by research-backed likely value.

Beyond Acts: the pipeline is book-agnostic. Romans and Hebrews are natural next targets (different lexical/syntactic profiles will stress-test the validator further). Eventually: full GNT.

A Hebrew equivalent is on the long-horizon roadmap. See HANDOFF.md Part 5 for detailed guidance on porting this approach to the Tanakh.
