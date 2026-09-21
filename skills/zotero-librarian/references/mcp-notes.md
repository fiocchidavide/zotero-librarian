# The Zotero MCP server: what exists, what doesn't, what bites

Verified against `zotero-mcp-server` running in local mode (`ZOTERO_LOCAL=true`) against
Zotero 7.

## Tool inventory

| Job | Tool | Notes |
|---|---|---|
| Create from DOI / URL / ISBN / BibTeX / CSL JSON / **file** | `zotero_add_item` | One tool. Takes `collections`, `tags`, `if_exists`, `attach_mode`. |
| Attach a file to an existing item | `zotero_attach_file` | Idempotent on filename + MD5. **Absolute paths only.** |
| Edit metadata | `zotero_update_item` | ⚠ see traps |
| Many items at once | `zotero_batch_update` | Tags, and `Key: value` lines in Extra |
| Move between collections | `zotero_set_item_collections` | Incremental `add_to`/`remove_from` |
| Re-parent an attachment | `zotero_set_item_parent` | Turns an orphan attachment into a child |
| Collections | `zotero_create_collection`, `zotero_update_collection`, `zotero_delete_collection` | |
| Find | `zotero_search_items`, `zotero_advanced_search`, `zotero_search_by_tag`, `zotero_search_by_citation_key`, `zotero_semantic_search` | |
| Inspect | `zotero_get_item_metadata`, `zotero_get_item_children`, `zotero_get_attachment_path` | |
| Read a PDF already in Zotero | `zotero_read_pdf_pages`, `zotero_get_pdf_outline`, `zotero_get_item_fulltext` | |
| Annotations / notes | `zotero_get_annotations`, `zotero_create_annotation`, `zotero_manage_note`, `zotero_synthesize_annotations` | |
| Index | `zotero_update_search_database` | Semantic search only; needs the `[semantic]` extra installed |
| Write gate | `zotero_write_capabilities`, `zotero_authorize_local_writes` | Call the first at preflight |

## What does not exist

- **No duplicate detection. No merge tool.** Dedup is your job: search by title/ISBN/DOI
  before creating, and hand genuine duplicates to the user to merge in the Zotero UI
  (Duplicate Items pane).
- **No saved-search creation.** Manual, in the UI.
- `zotero_search_items` **rejects an empty query** — you cannot list the whole library
  with it. Read `zotero.sqlite` directly for inventory work.

## Creating items with arbitrary metadata

There is no "create an empty item and set fields" tool. The way in is **CSL JSON**:

```
zotero_add_item(source=<path to .json>, source_type='csl_json',
                attach_mode='none', tags=[...])
```

Many entries per call. CSL → Zotero mapping handles `collection-title` → series,
`collection-number` → seriesNumber, `original-date` → originalDate, `contributor`,
`editor`, `translator`. A `DOI:` or `Rights:` line inside `note` is lifted into the real
field; the rest of `note` becomes Extra.

Use `attach_mode='none'` so the server doesn't go fetch an unrelated OA PDF, then attach
the real file with `zotero_attach_file`.

## Traps

### `tags=` replaces; `add_tags=` appends

`zotero_update_item(tags=[...])` **replaces the whole tag list**. Same for `collections=`
and `collection_names=`. Use `add_tags`/`remove_tags` and `zotero_set_item_collections`
unless you genuinely mean to replace.

### CSL JSON pins a junk citation key

Creating from CSL JSON writes the CSL `id` into the citation-key slot — as a
`Citation Key:` line in Extra on some paths, and into Zotero's native `citationKey` field
on others. Left alone, every import carries a key like `b117`.

After each batch, clear **both**:

```
zotero_batch_update(item_keys=[...], remove_keys=["Citation Key"])
zotero_update_item(item_key=..., fields={"citation_key": ""})
```

Empty is the correct resting state unless Better BibTeX is installed — nothing else
generates keys, and Zotero's own citation styles don't use them.

### `zotero_add_item(source_type='isbn')` is a seed, not truth

Documented as Open Library → Google Books. Measured: Open Library 92% but thin and
sentence-cased with no edition or series; the server's Google Books call is
unauthenticated and returns **HTTP 429 on every request**. Use it to seed an item at most;
the real pipeline is in [metadata.md](metadata.md).

### Deleting a collection is a hard delete

`zotero_delete_collection` is **not** a trash operation and **takes subcollections with
it**. Items survive (they stay in the library and in any other collection). Tag everything
in a collection *before* dissolving it, and take a database backup first.

### Child attachments leave their collections

When `zotero_set_item_parent` turns a top-level attachment into a child, it drops out of
any collection — child items can't be in collections. Put the *parent* into the collection
afterwards.

### Zotero runs SQLite in WAL mode

Any inspection that copies `zotero.sqlite` without `zotero.sqlite-wal` reads a **stale**
database and reports recent writes as missing. This produced a false "0 of 10 attachments"
during a verification pass, and an initial survey that undercounted the library by three
items.

```bash
cp ~/Zotero/zotero.sqlite      /tmp/z.sqlite
cp ~/Zotero/zotero.sqlite-wal  /tmp/z.sqlite-wal   # ← the part everyone forgets
```

Or verify through the MCP, which reads the live database.

### `zotero_update_item` says "No changes to apply" for already-correct values

Not an error and not a rejected field. Check with `zotero_get_item_metadata` before
concluding a field isn't supported.

### Semantic search is an optional extra

`zotero_update_search_database` fails with an install hint unless
`zotero-mcp-server[semantic]` is installed. Zotero's own full-text index builds
automatically in the app and is unaffected.

## Direct SQLite reading

For inventory, reconciliation and schema questions, read the database directly (with the
WAL, see above). Useful queries:

```sql
-- every item type that supports a given field
select it.typeName from itemTypeFields itf
 join itemTypes it on it.itemTypeID=itf.itemTypeID
 join fields f on f.fieldID=itf.fieldID
where f.fieldName='DOI';

-- top-level attachments with no parent (orphans: no metadata, uncitable)
select col.collectionName, i.key, ia.path
from collectionItems ci
 join collections col on col.collectionID=ci.collectionID
 join items i on i.itemID=ci.itemID
 join itemAttachments ia on ia.itemID=i.itemID
where ia.parentItemID is null
  and i.itemID not in (select itemID from deletedItems);

-- regular items with no creator
select i.key from items i join itemTypes it on it.itemTypeID=i.itemTypeID
where it.typeName not in ('attachment','note','annotation')
  and i.itemID not in (select itemID from deletedItems)
  and i.itemID not in (select itemID from itemCreators);
```

**Orphan attachments are worth hunting.** A library can accumulate bare PDFs dropped into
collections with no parent item: no title, no author, no date, uncitable and invisible to
metadata search. One real library had 22 of them.
