# Tested pipeline code

Working code, not pseudocode. Each module was run against 115 books and 95 distinct ISBNs
before landing here.

| file | what it does | validation |
|---|---|---|
| `sources.py` | one adapter per metadata source (Google Books, Crossref, Open Library, K10plus SRU, LoC SRU) with an on-disk response cache | 475 live queries; 99% of ISBNs resolved by ≥1 source |
| `norm.py` | `edition()` — MARC 250 / free text → an edition *number*, rejecting printings | 43/43 on the real strings the corpus returned |
| `clean.py` | the eight cleanup rules | each traceable to an observed defect |
| `resolve.py` | per-field waterfall, majority vote with priority tie-break | see references/metadata.md |
| `frontmatter.py` | front-matter text, page geometry, PNG rendering, cover-distrust signals | found 54 image-only covers and 19 whose geometry didn't match the body |

**Nothing here decides anything.** `resolve.py` ranks evidence; the metadata that lands is
the model's call after reading the front matter, with the PDF as final authority.

## Running

Stdlib only — no dependencies to install.

```bash
export GB_KEY=<google books api key>     # never commit this

cd "$CLAUDE_PLUGIN_ROOT/lib"             # or this directory, when working in the repo
uv run --no-project python -c "import sources; print(sources.gb('9780262048644'))"
```

Responses are cached on disk under `~/.cache/zotero-librarian/cache`, so re-running a
batch costs nothing. Set `SCR` to put the cache somewhere else.

`LoC` is included for completeness but is **dominated** — 21% coverage, nothing unique.
Don't wire it into new pipelines.
