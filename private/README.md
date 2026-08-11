# private/ — layout and conventions

**This folder is gitignored; only this README is tracked.** It holds session
artifacts and working notes that should not land in the public repository.

This stub exists so the folder's purpose survives even though its contents are
not committed. A directory that is entirely ignored leaves nothing behind when
it goes missing — which is exactly how two Greek corpora disappeared from
`readers-gnt` unnoticed on 2026-08-10.

## Layout

| Path | Holds |
|---|---|
| `03-sessions/` | Dated session artifacts, one file or subdirectory per session |
| `04-audits/` | Self-audits, scan outputs, diagnostic findings |
| `open-items.md` | Working queue for this repo |

Unlike the reader repos, this one is a morphology dashboard rather than a
colometric reader, so it does not carry the numbered five-tier layout and is not
expected to. Its shape follows what it does.

## Rules

- Our own durable analysis belongs in the repo proper, not here. `private/` is
  for working state — anything that should survive and be reviewable should be
  committed where git can diff it.
- Licensed third-party corpora may never be committed.
