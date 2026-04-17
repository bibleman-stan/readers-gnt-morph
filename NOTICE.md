# Third-Party Data Attribution

This repository vendors morphological and lexical data from several academic open-data projects. Each retains its original license. We are grateful to the maintainers for making this work possible.

## MorphGNT / SBLGNT

- **Source:** https://github.com/morphgnt/sblgnt
- **What it provides:** Every word of the Greek New Testament tagged with lemma and morphological parsing code.
- **License (morphology):** CC-BY-SA 3.0
- **License (underlying Greek text):** SBLGNT End User License Agreement — see data/morphgnt/LICENSE and the SBL Greek New Testament EULA. The SBLGNT base text is © The Society of Biblical Literature; use is governed by the SBL EULA.

## greek-inflexion (James Tauber)

- **Source:** https://github.com/jtauber/greek-inflexion
- **What it provides:** Principal-part stem database keyed by lemma. Essential for augment detection and formative extraction in morpheus.py.
- **License:** MIT

## morphological-lexicon (MorphGNT)

- **Source:** https://github.com/morphgnt/morphological-lexicon
- **What it provides:** NT lemma-to-gloss mapping with POS and Strong's numbers.
- **License:** MIT / CC-BY-SA (per project declarations)

## Substrate (Reader's GNT sense-lines)

- **Source:** https://github.com/bibleman-stan/readers-gnt (sibling project)
- **What it provides:** Colometric sense-line formatting of the GNT, consumed by `generate_chapter.py` as read-only input.
- **License:** As declared in the sibling repo.

---

If you redistribute this project, include this NOTICE.md with attribution unchanged, and respect the individual licenses of the vendored data sources.
