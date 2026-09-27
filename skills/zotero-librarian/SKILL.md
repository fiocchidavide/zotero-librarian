---
name: zotero-librarian
description: Import PDFs, papers, books and lecture notes into Zotero with metadata verified against the file itself rather than trusted from a catalogue, and keep the library on a flat collections-for-context, tags-for-topic model. Also handles lookups ("what does my library have on X"), retagging, and reorganising. Use whenever the user wants to add something to Zotero, search or ask about their Zotero library, or organise items in it.
---

# zotero-librarian

Zotero is the single library. There is no second destination to route to — everything
with a PDF goes here, and the only questions are *what is this exactly* and *where does
it belong*.

This skill exists because the obvious way to answer the first question is wrong. Looking
an ISBN up in a catalogue and writing down what comes back produces a library that is
confidently incorrect: wrong books, wrong years, wrong authors, and — worst — no signal
that anything is wrong. The method here was derived by migrating 115 books and measuring
every step; the numbers quoted throughout are from that run, not estimates.

**The one rule everything else follows from: the tools gather evidence, the model
decides, and the PDF is the final authority.**

## Trigger

- *"Import these,"* *"add this to Zotero,"* *"file these papers"* → the
  [Import runbook](#import-runbook).
- *"What does my library have on X,"* *"find my notes on Y"* →
  [Lookups](#lookups-ad-hoc), no runbook needed.
- *"Retag this,"* *"move these,"* *"clean up the collections"* →
  [Organising](#organising).

Just start; no need to re-confirm the plan first. Report progress as you go.

## Environment

Zotero desktop must be running. The MCP server talks to it locally
(`ZOTERO_LOCAL=true`) and reads `~/Zotero/zotero.sqlite` directly.

- **Reads** need Zotero's Settings → Advanced → "Allow other applications to communicate
  with Zotero" ticked. That is the user's job, not yours.
- **Writes** need a one-time in-app authorization. Call `zotero_write_capabilities` at
  the start of any run that will write; if it reports writes unauthorized, call
  `zotero_authorize_local_writes`, which pops a dialog for the user to approve. Don't
  attempt writes before it succeeds.
- **Google Books needs an API key** to be useful at all — see
  [references/metadata.md](references/metadata.md). Read it from `GB_KEY` in the
  environment. **Never hardcode it or commit it.**

If the server doesn't appear, check `/plugin` (is this plugin enabled?) and `/mcp`.

**Where `lib/` is.** Every `lib/*.py` named below lives at `${CLAUDE_PLUGIN_ROOT}/lib`,
which is set for you. It is stdlib-only — import it by putting that directory on the
path, and run it with `uv`:

```bash
uv run --no-project python -c "
import sys; sys.path.insert(0, '$CLAUDE_PLUGIN_ROOT/lib')
import sources, resolve
print(sources.gb('9780262048644'))
"
```

## Ground rules

- **Content is truth; the filename is a hint; the cover is an unsourced claim.**
- **Never write metadata you have not seen or corroborated.** An empty field is honest; a
  guessed one poisons every citation that uses it.
- **Agreement between sources is not truth.** Two catalogues agreeing with each other
  means they agree about a *catalogue record*, not about the file on disk. In the
  reference run, two independent sources agreed on a completely different book.
- **New items go to `Inbox/` and nowhere else.** Only the user knows what context an item
  belongs to.
- **Never delete or merge without confirming.** There is no merge tool anyway (see
  [references/mcp-notes.md](references/mcp-notes.md)); propose, and let the user merge in
  the Zotero UI.
- **Stop after repeated write failures** rather than looping.

## Import runbook

### 0. Preflight (once per run)

`zotero_write_capabilities`. If writes aren't authorized, `zotero_authorize_local_writes`
and wait. Confirm `mutool` is on PATH (it is the only PDF tool needed — see
[Reading the file](#1-read-the-file)).

### Per file

#### 1. Read the file

```
mutool info <pdf>                              page count — the only trustworthy source
mutool draw -F txt -o - <pdf> 1-10             front matter text layer, if any
mutool draw -F png -r 150 -o p%d.png <pdf> 1-10   render when there is no text layer
```

**You are the OCR.** No `tesseract`/`ocrmypdf` is needed: render the pages and look at
them. It is effectively free — page 3 of a 216 MB scan renders in 0.03 s.

Render rather than extract when: the text layer is empty or garbled; the cover is
image-only; or extracted author order contradicts the surrounding evidence
(**extraction returns text in *layout* order, which can invert an author list**).

`lib/frontmatter.py` gives you `page_text`, `render`, `page_geometry`,
`cover_suspicion` and `needs_visual_read`.

#### 2. Classify

Book signals: ISBN on a copyright page, table of contents, "Nth edition", a
dedication/preface, >150 pages. Paper signals: DOI, abstract, references section, a
journal or conference name, <60 pages. Genuinely ambiguous (thesis, book chapter, tech
report) → import anyway, tag `needs-review`, and say so.

#### 3. Extract identifiers from the text you just read

```
ISBN   /\b97[89][\d -]{10,}\b|\b\d{9}[\dXx]\b/   → validate the checksum
DOI    /\b10\.\d{4,9}\/[-._;()\/:a-z0-9]+\b/i
arXiv  /arXiv:\s*\d{4}\.\d{4,5}/
```

#### 4. Gather evidence — never decide here

- **DOI or arXiv id** → `zotero_add_item(source=<doi|url>)`. CrossRef metadata,
  authoritative; always prefer this when you have one.
- **ISBN** → the fan-out in `lib/sources.py`, then `lib/resolve.py`.
- **Nothing** → the author's own page is authoritative for self-published notes. Never
  invent a publisher; ask.

**Do not use `zotero_add_item(source_type='isbn')` as a source of truth** — see
[references/mcp-notes.md](references/mcp-notes.md).

#### 5. Adjudicate — this is where the metadata is actually decided

Read the front matter and settle every field against it, **for every item, no matter how
clean the candidates look**. Order of authority:

```
1. the PDF's typeset title page and its verso (copyright page)   ← decisive
2. the rest of the front matter: series page, preface, TOC
3. external sources — for what the PDF omits, and to corroborate
4. any prior local record — a previous judgement, not a fact
5. page 1 / the cover image                                      ← lowest
```

Resolution: **PDF states it → PDF wins**, and the override goes in `extra` so the
decision stays auditable. PDF silent and sources agree → write it. PDF silent and sources
conflict → leave empty, tag `needs-review`, surface both values. Never pick silently.

The judgements that are yours and cannot be delegated to a rule are listed in
[references/metadata.md](references/metadata.md#judgements-that-are-yours).

#### 6. Write

```
zotero_add_item(source=<absolute path>, collections=['Inbox'], tags=[...], if_exists='file')
→ zotero_update_item(...) for anything extraction got wrong
```

Then **strip the junk citation key** (see mcp-notes) and verify: `zotero_get_item_children`
for the attachment, and an MD5 check against the source file if the original is still on
disk.

## Structure

Full model and the controlled vocabulary: [references/structure.md](references/structure.md).

```
Inbox/                  everything new; should trend to empty
Courses/<inst>/<course>
Projects/<name>
Archive/
```

That is the whole collection tree. **Items live at the library root** unless a course or
project actually uses them. Classification is tags:

- 1–3 `topic:` tags from the controlled vocabulary. A term that isn't in the list is a
  **vocabulary change to propose**, not a tag to invent silently.
- exactly one `kind:` tag.
- `needs-review` whenever a field failed the gate.

## Lookups (ad hoc)

No runbook. Use `zotero_search_items`, `zotero_advanced_search`, `zotero_search_by_tag`,
`zotero_get_item_fulltext`, `zotero_get_annotations`, `zotero_get_notes`,
`zotero_get_collections` / `zotero_get_collection_items`, `zotero_get_tags`, and
`zotero_semantic_search` if keyword search comes up empty. Quote what the source actually
says; don't paraphrase from the title.

## Organising

No fixed script — use the read/write tools directly, keeping the two standing rules:
content over filenames, and never delete or merge without confirming. Watch the
[tag-replacement trap](references/mcp-notes.md#traps) when retagging.

## Bookkeeping

For runs over ~10 files, keep an append-only JSONL ledger — one line per state
transition (`intent`, `created`, `attached`, `tagged`, `verified`) — so an interrupted run
resumes cleanly. Write the `intent` line *before* the create.

**The durable safety net is not the ledger but the library itself:** put
`imported: <date>` (and any source id) in `extra`, and tag the run. Even with the ledger
deleted, the run can be reconstructed by listing that tag. Always search for an existing
item by that key before creating — `if_exists` only dedupes on DOI/ISBN/URL, which
self-published material doesn't have.

## Reference

- [references/metadata.md](references/metadata.md) — which source for which field, with
  measured coverage; the traps; the cleanup rules; what only the PDF can tell you.
- [references/structure.md](references/structure.md) — collections, the `topic:`/`kind:`
  vocabulary, saved searches, item types and field conventions.
- [references/mcp-notes.md](references/mcp-notes.md) — the real tool inventory, what
  doesn't exist, and the API traps.
- `${CLAUDE_PLUGIN_ROOT}/lib/` — tested code. Don't reimplement it.
