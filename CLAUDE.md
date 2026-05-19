# readers-gnt-morph — Claude Code Instructions (thin stub)

This repo is operated by the **unified user-home orchestrator-Claude** at `C:\Users\bibleman\`. Stan opens VSCode at user-home, not at this repo.

If you are a Claude that spawned in this workspace (VSCode opened at this repo): **hand off**. Tell Stan to switch to a vault-Claude window at `C:\Users\bibleman\`. The unified Claude has full cross-repo context; per-repo Claudes don't.

## What this project is (for collaborators / forks)

Browser-based morpheme reader for the Greek New Testament. Each Greek word decomposed into morphological pieces (prefix → augment → stem → formative → ending) with color-coded toggleable layers. Live at **morph.gnt-reader.com** — full GNT, 27 books, 260 chapters published. Morphological decomposition validated 99.5%+ corpus-wide.

- **Sibling to**: `readers-gnt` (consumes its sense-lines; never writes to it)
- **Data**: `data/chapter-jsons/` (per-chapter morpheme decompositions); vendored corpora under `data/`
- **Build**: `src/bulk_generate.py` (whole-GNT regen in ~23s); `src/generate_chapter.py --book X` per chapter
- **Validation**: `src/validate_chapter.py` (morphology), `src/validate_glosses.py` (English)
- **Live deploy**: morph.gnt-reader.com (GitHub Pages from `docs/` folder)

## For more detail

- **Full prior operational discipline** (241-line CLAUDE.md, authored before the 2026-05-19 vault unification) is archived at [`_archive/2026-05-19-pre-unification/CLAUDE.md`](_archive/2026-05-19-pre-unification/CLAUDE.md). Includes cubicle-boundary rules (read readers-gnt sense-lines; never write), validator workflow, the morph-specific decomposition standards.
- **Project retrospective + architecture**: [HANDOFF.md](HANDOFF.md) — full project trajectory, 8 lessons learned, Resumption Checklist in Part 6.5.
- **Vendored data attribution**: [NOTICE.md](NOTICE.md).
- **Canonical methodology** (cross-corpus): `~/repos/atu-method/docs/`.

## Migration arc

This thin stub is part of the **master-blaster vault unification** (2026-05-19). Stan retired per-repo Claudes in favor of a single orchestrator at `C:\Users\bibleman\`. See `~/.claude/projects/C--Users-bibleman/memory/_named_arcs.md` for the arc.
