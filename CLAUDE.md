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

Self-contained — the overseer coordination layer retired 2026-04-20. Claude answers only to Stan. No shared source file; this section is the spec.

### CHECK-IN at session start

When Stan signals start-of-session (including short wakes like "hey wake up"), before any substantive work, read the files below in order, then self-report per-file.

**MANDATORY (read every wake, no exceptions):**
1. **This CLAUDE.md in full** — active rules may have changed
2. **`private/open-items.md`** — live work queue
3. **[HANDOFF.md](HANDOFF.md)** — architectural retrospective; Resumption Checklist in Part 6.5 is most load-bearing on a fresh wake
4. **`C:\vaults-nano\my_brain\00_Inbox\claude-brainstorming.md`** — mobile→desktop bridge; morph-scope items only (never delete; leave non-morph items untouched)
5. **`git log --oneline -10`** — any unfamiliar commit is a state change to understand before working
6. **`PYTHONIOENCODING=utf-8 python src/sync_senselines.py`** (report-only) — surface any `readers-gnt` sense-line drift since last session; if drift exists, default to `--regen` without asking

**CONSULT-ON-TRIGGER (evaluate; a silent skip is a check-in failure):**
- [NOTICE.md](NOTICE.md) — **trigger:** touching vendored data or making licensing-relevant changes. **Skip when:** code / pipeline / UX / deployment work with no vendored-corpus touching.
- Validator (`PYTHONIOENCODING=utf-8 python src/validate_chapter.py build/acts/9.json`) — **trigger:** first wake on a new machine, OR pipeline state suspected to have shifted (morpheus.py / inflect_gloss.py / generator touched since last verified run). **Skip when:** recent clean run in session log.

**SELF-REPORT format** — one line per file in a check-in message, before your first substantive response:

> **Checked in.**
> - CLAUDE.md — read
> - open-items.md — read; [N items / changes since last wrap]
> - HANDOFF.md — read; [new entries or "tail unchanged"]
> - brainstorming inbox — read; [N items / disposition]
> - git log — [N new commits; surprises or "nothing unexpected"]
> - sync_senselines — [N stale / clean]
> - NOTICE.md — [read / skipped]; [trigger evaluation]
> - validator — [read / skipped]; [trigger evaluation]
>
> [One-line focus candidate + ask.]

One sentence max per line. Purpose: prove the read happened; make skips auditable.

### WRAP-UP at session end

When Stan signals "wrap it up" (or equivalent), in order:

1. **Create the session folder:** `private/03-sessions/<YYYY-MM-DD>-<brief_description>/`. Date = calendar day of the first commit in the session (midnight-spanning sessions take the commit date). `brief_description` is short, lowercase, hyphenated.
2. **Verbatim transcript:** copy the Claude Code session file (`C:\Users\bibleman\.claude\projects\c--Users-bibleman-repos-readers-gnt-morph\<session-id>.jsonl` — most recent by mtime if uncertain) into the session folder as `transcript.jsonl`. This is the true verbatim — every user/assistant turn + tool call. Do not edit or paraphrase it.
3. **Session notes** at `<folder>/session-notes.md`. What it should contain:
   - What you built or fixed
   - What validator said before and after (if pipeline-relevant)
   - Any new edge cases surfaced
   - Decisions Stan made — preserve load-bearing quotes verbatim
   - **Self-log of discipline failures Stan caught.** Name each. If ≥2 share a common underlying mode (over-structuring, alignment-skip, imposing-vs-revealing, pattern-matching-over-diagnostic, rule-multiplication), say so explicitly.
   - **Any proposed rule / framing / claim walked back** — with the reason (anti-over-claim discipline).
   - **Workflow use-count** — if a recurring workflow was used 3+ times, note the count; repeated use = validation.
4. **Update `private/open-items.md`** — mark applied items with commit hashes and date; add new items surfaced this session; prune the list when items land.
5. **Update HANDOFF.md** — ONLY for architectural-retrospective additions (trajectory, lessons learned, resumption-checklist changes). Per-session run-downs belong in session notes, not HANDOFF.md.
6. **Wrap-up message** to Stan (4-8 lines): commits landing, files touched, items closed, items opened, session-folder path, anything to flag.
7. **Commit.**

### Context-aware self-discipline

Compaction is the silent equivalent of "wrap it up." Thresholds:

- **~50% context remaining — informal checkpoint.** Commit WIP code even if incomplete, save in-flight batch state to a file, note session-so-far in the session folder. Don't stop working.
- **~40% context remaining — defensive checkpoint, NOT hard wrap.** Write out anything that only lives in memory (partial notes, batch aggregations, reasoning chains). **Continue deliverable work** — execution-heavy sessions (full-GNT regens, horde dispatches) should run through this threshold, not be interrupted by ceremony. Tell Stan you've crossed 40% so he can decide whether to continue in a fresh session.
- **~25% context remaining — hard wrap.** Finish only the wrap-up. Don't start new work. The runway between 25% and auto-compact is the margin for wrap-up itself.

When in doubt, write it down. Files survive compaction; working memory does not.

### Compaction-resume protocol

When the conversation resumes from an auto-compaction summary rather than a live session start:

- **In-flight continuation** (Stan's first post-compaction message is a direct continuation of the pre-compaction task — "keep going on X", "back to Y"): **minimal 3-file check-in** — this CLAUDE.md's active-rules section, `private/open-items.md`, and the brainstorming inbox. Then pick up the task. Do NOT execute the full CHECK-IN.
- **Fresh-start signal** ("new session", "hey wake up", "let's work on X today"): execute the full CHECK-IN above.
- **Ambiguous:** ask Stan in one line whether to treat as resume-in-flight or fresh start.

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
