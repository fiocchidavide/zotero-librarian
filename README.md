# zotero-librarian

A Claude Code plugin for keeping a personal Zotero library honest.

Zotero is the single library: everything with a PDF goes in it, and the only questions are
*what is this exactly* and *where does it belong*.

The obvious way to answer the first question is wrong. Looking an ISBN up in a catalogue
and writing down what comes back produces a library that is confidently incorrect — wrong
books, wrong years, wrong authors, and no signal that anything is off. This plugin encodes
a different method:

> **The tools gather evidence, the model decides, and the PDF is the final authority.**

Everything in `references/` is measured rather than assumed. The figures come from
migrating a 115-book library: 475 live API queries across five metadata sources, a
resolver run over every book, then reading all 115 PDFs. That run found three confident
wrong-book matches (one where two independent sources agreed with each other), nine
records whose author field held something that was not an author — a PDF creation
timestamp, a scanner's handle, a publisher recorded as a person — and a dozen contributors
no catalogue listed.

## Install

Add as a user-level plugin, then enable it:

```bash
git clone git@github.com:fiocchidavide/zotero-librarian.git ~/.claude/skills/zotero-librarian
```

Check `/plugin` that `zotero-librarian` is enabled and `/mcp` that the `zotero` server is
connected.

## Requirements

- **Zotero 7** running, with Settings → Advanced → "Allow other applications to
  communicate with Zotero" enabled. Writes need a one-time in-app authorization, which the
  skill will prompt for.
- **`mutool`** (from MuPDF) on PATH — the only PDF tool needed. No OCR toolchain is
  required; pages are rendered and read directly.
- **A Google Books API key** in `GB_KEY`. Unauthenticated, Google Books returns HTTP 429
  on every request and is useless; with a key it is the single best metadata source.
  Put it in `.env` (gitignored) or your shell profile — never in the repo.

## Layout

```
skills/zotero-librarian/
  SKILL.md                    the runbook
  references/
    metadata.md               source coverage, the traps, the cleanup rules
    structure.md              collections, tag vocabulary, saved searches, fields
    mcp-notes.md              real tool inventory, what doesn't exist, API traps
lib/                          tested code — don't reimplement
  sources.py                  five source adapters + on-disk response cache
  norm.py                     edition() — MARC 250 / free text -> edition NUMBER
  clean.py                    the eight cleanup rules
  resolve.py                  per-field waterfall, majority vote with priority tie-break
  frontmatter.py              front-matter text, page geometry, rendering, cover signals
```

## The short version

- **No single metadata source suffices.** Google Books owns title/authors/pages/abstract
  and has *no* edition, series or place — ever. K10plus is the only real source for those
  three. Crossref covers a third but gives DOIs and structured names.
- **Never take a year from a library catalogue** — it dates the printing, not the edition.
  Wrong in 37% of comparable records, by up to 26 years.
- **Agreement is not truth.** Cross-checking the external title against the PDF is a hard
  gate, not a nicety.
- **A printing is not an edition**, and an anniversary edition is not edition 20.
- **The cover is the least trustworthy page.** 47% of one corpus had image-only covers,
  some scraped from aggregators, watermark and all — invisible to text extraction.
- **Collections are context; tags are topic.** Items live at the library root; `Inbox`,
  `Courses`, `Projects`, `Archive` is the whole tree.

## License

Personal tooling; no warranty.
