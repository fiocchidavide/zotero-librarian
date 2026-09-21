# Library structure

**The model in one sentence:** collections answer *"what was I doing when I needed this"*;
tags answer *"what is this about"*; saved searches turn tag queries into the folders you
actually click.

## Collections — context only

```
Inbox/                      everything new lands here; should trend to empty
Courses/
  ETH/<course name>
  EPFL/<course name>
  MIT/<course name>
  UniTO/<course name>
Projects/<project name>     a thesis, a paper being written, a reading group
Archive/                    superseded editions, things you're done with
```

That is the whole tree. **Items live at the library root with no collection.** An item
joins a collection only when a course or project actually uses it — and it can join
several, because collections are membership, not location.

Deliberately *not* present: a topic hierarchy. Topic lives in tags, where an item can hold
several without a filing decision and without a cross-cutting work needing an arbitrary
single home.

## Tags — the real search surface

Three namespaces, colon-prefixed so the tag selector groups them alphabetically.

### `topic:` — what it's about

1–3 per item. More than three means the vocabulary needs a new term, not a longer list.
**A term not on this list is a vocabulary change to propose, not a tag to invent.**

```
Mathematics
  real-analysis  complex-analysis  functional-analysis  measure-theory
  probability  stochastic-processes  statistics  causal-inference
  linear-algebra  abstract-algebra  number-theory  algebraic-geometry
  computational-geometry  discrete-mathematics  calculus
  numerical-analysis  optimization  logic  information-theory

Computer science
  algorithms  complexity  computability  automata
  cryptography  security  privacy
  networking  operating-systems  computer-architecture  embedded  electronics
  concurrency  databases  systems-administration
  machine-learning  nlp  ai  data-science  quantum-computing
  software-engineering  programming  signal-processing

Other
  history-of-computing  cognitive-science  languages
```

45 terms in live use. Eight of them (`discrete-mathematics`, `functional-analysis`,
`computational-geometry`, `quantum-computing`, `concurrency`, `databases`,
`signal-processing`, `electronics`) were added while cataloguing lecture notes and
hardware material — a book-derived vocabulary under-serves course material, so expect to
extend it there.

### `kind:` — what sort of object it is

Exactly one per item.

```
kind:textbook       a course-shaped book with exercises
kind:monograph      a research-level treatment
kind:lecture-notes  course handouts, author-hosted notes
kind:reference      handbooks, pocket references, language references
kind:manual         tool documentation
kind:solutions      instructor's manuals, solution sets
kind:popular        trade books
kind:paper          journal articles, preprints, conference papers
```

### Status — coloured

Colour these 1–3 in Zotero so they get keyboard shortcuts and show as dots in the item
list.

```
★ reading       what's open right now
to-read         the actual queue
needs-review    metadata you don't trust yet
```

### Housekeeping

Tag any bulk import with a run tag (`migration:<name>`, `import:<date>`) — one click
selects the whole run for inspection or rollback.

**Strip auto-imported arXiv subject tags** ("Computer Science - Machine Learning"). They
are noise from a different namespace and will swamp a deliberate vocabulary. Leave
hand-written tags alone.

## Saved searches — the folders you click

⚠ **The MCP server cannot create saved searches**, and writing them into `zotero.sqlite`
behind the running app risks corruption. These are a **manual one-time job** in the Zotero
UI (File → New Saved Search), about ten minutes. Under this model they *are* the folders,
so the step is not optional.

| Name | Condition |
|---|---|
| **Analysis** | Tag is `topic:real-analysis` **or** `topic:complex-analysis` **or** `topic:measure-theory` |
| **Algebra & Number Theory** | `topic:abstract-algebra` or `topic:linear-algebra` or `topic:number-theory` or `topic:algebraic-geometry` |
| **Probability & Statistics** | `topic:probability` or `topic:statistics` or `topic:stochastic-processes` or `topic:causal-inference` |
| **Theory of Computation** | `topic:complexity` or `topic:computability` or `topic:automata` or `topic:algorithms` |
| **Security & Crypto** | `topic:cryptography` or `topic:security` or `topic:privacy` |
| **Systems** | `topic:networking` or `topic:operating-systems` or `topic:computer-architecture` or `topic:embedded` |
| **AI/ML** | `topic:machine-learning` or `topic:nlp` or `topic:ai` |
| **Needs attention** | Tag is `needs-review` **or** Attachment File Type does not contain PDF |
| **Reading queue** | Tag is `to-read` or `★ reading` |
| **Italian** | Language contains `it` |
| **Added this month** | Date Added is in the last 30 days |

## Item types

| Situation | type |
|---|---|
| Published book with ISBN | `book` |
| Author-hosted notes | `document` |
| Pre-publication draft | `manuscript` |
| Papers | `journalArticle` / `preprint` / `conferencePaper` |

⚠ **Not every type carries every field.** `document` has **no `numPages` and no
`edition`** — for versioned notes, record `Version:` and `Pages:` as Extra lines instead.
`manuscript` has `numPages` but no `publisher`. Only `book` has the full set, which is why
a published-but-draft PDF is often better as `book` with a note than as `manuscript`.

Check before assuming:

```sql
select f.fieldName from itemTypeFields itf
 join itemTypes it on it.itemTypeID=itf.itemTypeID
 join fields f on f.fieldID=itf.fieldID
where it.typeName='document';
```

## Field conventions

These are what make the bibliography output correct.

- **`title`** — full title including subtitle after a colon, exactly as printed. The
  edition does **not** belong in the title.
- **`shortTitle`** — the main title before the colon. Makes `\cite` output readable.
- **`creators`** — order from the title page. Particles (`van Oorschot`, `Le Gall`,
  `González Vasco`) stay in `lastName`.
- **`edition`** — a bare number (`4`). Free text only when the edition genuinely isn't
  numbered (`0.1Gβ`, `Annual Edition 2025`).
- **`series` / `seriesNumber`** — prefer the PDF's series page; it often carries the
  volume number no catalogue has.
- **`numPages`** — from `mutool info`. The file is the only truth about the file.
- **`language`** — `en` / `it` / `de`.
- **`DOI`** — **a real field on every Zotero item type, `book` included.** Never put a DOI
  in Extra.
- **`originalDate`** — for translations, the original's year.
- **`rights`** — `CC BY 4.0`, `Open access` where the copyright page says so.
- **`url`** — anything author-hosted or open access.
- **`abstractNote`** — only a genuine abstract. Empty beats marketing copy.
- **`extra`** — only what has no field of its own, one `Key: value` per line:
  ```
  imported: 2026-09-21
  Version: 3.08 (19 July 2020)
  Pages: 166
  ```
  plus provenance prose: overrides you made against a source, aggregator watermarks, and
  anything a future reader would need to re-check your judgement.

**Useful mechanic:** a `DOI:` or `Rights:` line written into a CSL JSON `note` is parsed
out into the proper field on import. Extra keeps only the remainder.
