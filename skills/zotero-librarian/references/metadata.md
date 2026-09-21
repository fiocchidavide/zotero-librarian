# Metadata: the recipe, the traps, the tricks

Everything here is measured, not assumed. The figures come from a migration of 115 books:
95 distinct ISBNs × 5 sources = 475 live queries, then the resolver run over every book,
then reading all 115 PDFs.

## 1. Which source for which field

No single source is sufficient, and the split is sharp and non-obvious.

| field | crossref | k10plus | loc | **google** | openlib | any |
|---|---:|---:|---:|---:|---:|---:|
| **record found** | 34% | 89% | 21% | **94%** | 92% | **99%** |
| title | 34% | 89% | 21% | **94%** | 92% | 99% |
| authors | 29% | 89% | 21% | **94%** | 80% | 97% |
| publisher | 34% | **89%** | 0% | 77% | 92% | 96% |
| year | 34% | 88% ⚠ | 21% | **92%** | 91% | 99% |
| **edition** | 8% | **58%** | 13% | **0%** | 25% | 63% |
| **series** | 18% | **46%** | 6% | **0%** | 9% | 49% |
| **place** | 0% | **89%** | 15% | **0%** | 31% | 89% |
| pages | 0% | 22% | 16% | **74%** | 72% | 93% |
| abstract | 2% | 44% | 5% | **86%** | 16% | 91% |

- **Google Books** owns title, authors, pages, language, abstract. It has **no edition,
  no series, no place — ever**.
- **K10plus** (the German union catalogue, free SRU endpoint, no key) is the *only* real
  source for **edition, series and place**.
- **Crossref** covers a third, but when it hits it gives a DOI and structured
  `given`/`family` names that sidestep all name-splitting guesswork.
- **Open Library** is broad but thin — sentence-case titles, no edition, sometimes zero
  authors.
- **Library of Congress is dominated**: 21% coverage, nothing unique. Don't wire it in.

**Google Books requires an API key.** Unauthenticated it returns `HTTP 429` on *every*
request — 0% coverage. With a key it is the single best source. Put it in `GB_KEY`.

Only 1 ISBN in 95 resolved nowhere.

## 2. Resolution rule

**Majority vote first; source priority only as the tie-break.** Three sources agreeing
beat one high-priority source.

Measured: Crossref alone dated Cover & Thomas 2005 while Google Books, LoC and the PDF's
own copyright page all said 2006. A priority-only waterfall picks 2005 and is wrong.

Implemented in `lib/resolve.py`.

## 3. ⚠ The traps

### A library catalogue dates the *printing*, not the edition

**Wrong in 24 of 65 comparable records (37%)**, by up to 26 years:

| book | k10plus | truth | MARC 250 field |
|---|---:|---:|---|
| Hodge Cycles, Motives, and Shimura Varieties | 2008 | 1982 | `[Nachdr.]` |
| Rudin, *Real and Complex Analysis* | 2013 | 1987 | `3. ed., internat. ed., [Nachdr.]` |
| Boyd & Vandenberghe, *Convex Optimization* | 2023 | 2004 | `Version 29` |
| Arora & Barak, *Computational Complexity* | 2016 | 2009 | `4th printing 2016` |

→ **Never take `year` from a catalogue.** A hard `NEVER` rule in `lib/resolve.py`.

### An ISBN can resolve to a completely different book

*Basic German: A Grammar and Workbook*, ISBN `9780415283090`, returns *An Introduction to
Ethics for Health Professionals* — from **two independent sources that agreed with each
other**. The local ISBN was simply wrong; the copyright page prints `0-415-28404-X`.

Separately, Crossref returns DOI `10.1142/11870` *titled "Elliptic Curves"* for the
*Fields and Galois Theory* ISBN. A DOI that resolves to the wrong work is worse than no
DOI: **omit it**.

→ **Cross-checking the external title against the PDF is a hard gate.** It is the only
thing that catches this class of error.

### A printing is not an edition

MARC 250 yields `32. printing`, `[Nachdr.]`, `Ninth printing`, `Corr. 2. print., [repr.]`,
`4th printing 2016`. Copying these as editions was wrong 13 times out of 59.

`lib/norm.py::edition()` drops printing-only clauses, parses mixed ones
(`4. ed., 4. print` → 4), handles `4a edizione` → 4, and correctly refuses to turn
`20th-anniversary ed.` into edition 20 — an occasion is not a number. **43/43** on every
edition string the corpus produced.

Subtler variant: a printing *date*. *Clean Code*'s copyright page says "© 2009" and, four
lines later, "First printing July, 2008".

### Bookseller and platform junk leaks into catalogue records

Observed, all silently wrong: `Computer Networks [RENTAL EDITION]`, `Internet e reti.
Fondamenti. Ediz. MyLab`, `Introduction to Algorithms, fourth edition` (edition in the
title), series `Always learning` (a Pearson slogan), series `SpringerLink` (a platform),
place `Bosten` (a typo *in the catalogue*), place `Heidelberg` on a San Francisco
publisher, place `Australia` from a multi-country imprint line, place `Beijing` from an
O'Reilly colophon.

### Catalogues are sentence-case

k10plus 17% title-case, LoC 0%, Open Library 71%, Google Books 98%, Crossref 100%.
`Principles of mathematical analysis` is a cataloguing convention, not the printed title.
Reject catalogue casing when a better source exists.

### The cover is the least trustworthy page

**47% of the corpus had an image-only page 1**, and **19 of 115 had a page-1 geometry that
didn't match the body** — covers fetched separately from a retailer or aggregator and
glued on. Observed watermarks: `http://freepdf-books.com`, `scanned by dataCore`.

The freepdf one was **part of the cover image**, invisible to text extraction. Only
looking at the page finds these. `lib/frontmatter.py::cover_suspicion()` tells you which
pages to look at first.

### Text-extraction order is not reading order

`mutool draw -F txt` emits text in layout order. On *TCP/IP Illustrated Vol 2* it returned
"Stevens, Wright"; the rendered cover reads "Gary R. Wright / W. Richard Stevens".

### Copyright lines list every edition

`© 1996, 2005, 2024` — take the **latest**, not the first. Getting this wrong misdated 11
books. `lib/clean.py::year_from_pdf()`.

## 4. The eight cleanup rules (`lib/clean.py`)

Each traceable to an observed defect:

1. Google Books splits the subtitle into its own field → rejoin.
2. Crossref returns XML-escaped text (`&amp;`) → unescape.
3. Catalogue titles are sentence-case → reject in favour of the printed casing.
4. Copyright lines list every edition → take the latest year.
5. Google Books appends the edition to the title → strip it into `edition`.
6. K10plus puts platform names in the series field → blocklist.
7. MARC place artefacts (`New York [u.a.]`) → strip.
8. Names arrive in three shapes → `{firstName, lastName}`, particles handled in both
   directions (`Oorschot, Paul C. van` → `van Oorschot`). **Spanish double surnames stay
   ambiguous by rule — flag, don't guess** (`González Vasco` was split to `Vasco`).

## 5. What only the PDF can tell you

This is the payoff. In the reference run, reading the files produced:

- **Nine records whose author field held something that was not an author**: a PDF
  creation timestamp (`09:15:55, R. Rajagopal 4716 2000 Dec 22`), a scanner's handle
  (`Jfly`), a retyper's handle (`althea`), a TI literature number
  (`Texas Instruments, Incorporated [SLYW038,C`), the literal placeholder `Author-names`,
  a publisher recorded as a person (`Project, Open Logic`), a bare surname (`rumbaugh`),
  and a person who wasn't an author of the book at all.
- **A dozen people no external source listed**: five translators, two editors of an
  Italian edition, three of four co-authors on a Springer LNM volume, and co-authors
  dropped by every catalogue.
- **Kind errors, not detail errors**: edited volumes recorded as authored ones ("edited
  by …" on the title page), and editors recorded as authors.
- **Author-supplied metadata inside the file.** Some authors embed a BibTeX block
  (`@misc{...}` with title-with-version, year, page count) — better than any catalogue,
  and it confirmed two print-on-demand ISBNs nothing else could verify. Others print a
  suggested citation outright. **Always grep the front matter for `@misc`/`@book` and for
  "cite".**
- **Drafts masquerading as editions.** A PDF whose dateline is years after its copyright
  is the author's rolling version, not the print edition. Date the artifact, note the
  edition of record.

### Judgements that are yours

No rule suffices; decide these by reading:

| decision | why |
|---|---|
| title vs. subtitle | where the colon goes; whether a line is a subtitle or a series name |
| edition vs. printing vs. impression | "Fifth printing with corrections" of a 2nd edition is edition 2 |
| **which** year | copyright, first-publication, this-printing and online-first all appear |
| author order and ambiguous name splits | the title page's typography settles it |
| item type | `book` vs `document` vs `manuscript` turns on whether it was actually published |
| is this the edition it claims | retypes, drafts, "penultimate versions" |
| is the abstract worth keeping | some are marketing copy that doesn't belong in a record |
| is a duplicate really a duplicate | one work in two artifacts → one item, two attachments |

## 6. Operational notes

- Send `?mailto=` to Crossref (polite pool, better rate limits).
- **Follow redirects on Open Library**: `/isbn/X.json` 302s to `/books/OL…M.json`, and a
  non-following client reports a false miss. This produced a bogus "0% coverage" reading
  on a first pass.
- Cache every response (`lib/sources.py` does) so a batch is re-runnable at zero cost.
- For Crossref books: `filter=isbn:<i>,type:book` first; on a miss take any hit's DOI,
  strip the `_<n>` chapter suffix to get the container DOI, and accept only if its type is
  `book`/`monograph`/`reference-book`/`edited-book`.
- A filesystem path built from a database record may not be the real path — applications
  sanitise filenames (an apostrophe becoming `_`, for instance). A silent path failure
  looks exactly like an unreadable scan. If a file "has no front matter", check that you
  opened the right file.
