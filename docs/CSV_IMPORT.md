# Curriculum CSV import

The admin import accepts a CSV of **vocabulary** or **grammar**. It is forgiving
about column names and extra columns — you don't have to match headers exactly —
but a few fields are genuinely required. Files import as **drafts**; nothing
publishes automatically.

## What's required

**Vocabulary**
- a **term** column — any of: `Word`, `Term`, `Vocab`, `Entry`, `Phrase`
- **Translation** (the English gloss)
- **Level** — any of: `Level`, `Unit`, `Module`
- **Batch** — any of: `Batch`, `Lesson` (which of the 4 themed batches, 1–4)

**Grammar**
- a **term** column — any of: `Grammar`, `Word`, `Term`, `Item`
- **Level** — any of: `Level`, `Unit`, `Module`
- Translation is **optional**: if `Translation` is blank the importer uses the
  **`Meaning`** column as the gloss (grammar sheets usually keep it there).

## Optional columns (imported if present, ignored if absent)

`Pronunciation` · `IPA` · `PoS` (part of speech) · `Meaning` · `Structure`
(grammar pattern) · `Synonyms` · `Variants` · `Castilian` · `Example` ·
`Example Tran.` · `Tags`. Any column the importer doesn't recognise is simply
ignored, so you can keep working notes in the sheet.

## Header aliases

Headers are matched case-insensitively and ignore extra spaces, and these
synonyms are accepted:

| Canonical | Also accepted |
|---|---|
| Word / term | Grammar, Term, Item, Vocab, Entry, Phrase |
| Translation | English, Gloss |
| Level | Unit, Module |
| Batch | Lesson, Group |
| PoS | Part of Speech, Word Type, Type |
| Structure | Pattern, Form |
| Meaning | Notes, Explanation, Description, Definition, Usage |
| Variants | Variations |
| Castilian | Spain, Peninsular |

## Formatting rules

- **Encoding:** UTF-8 (a BOM is fine). Accents like `qué`, `añadir` must be UTF-8.
- **Size:** up to 5 MB per file.
- **Empty cells:** blank, `N/A`, `na`, `none`, and `-` are all treated as empty.
- **Commas inside a cell:** wrap the cell in double quotes, e.g.
  `"Articles, nouns, and adjectives agree…"`. Spreadsheets do this automatically
  on export.
- **Lists** (Synonyms, Variants): comma-separated inside the cell, e.g.
  `"corro, corres, corre"`.

## Re-importing = editing (idempotent)

Import is keyed on (level, normalised term), so re-importing the same file
**updates** existing draft rows instead of duplicating them. This means, until
the in-app editor lands, your CSV doubles as the editor:

- **Add** an item → add a row.
- **Edit** an item → change its cells and re-import.
- **Move** an item to another unit/batch → change its `Level` / `Batch` and
  re-import.

Rows you've already moved past draft (in-review / published / archived) are not
overwritten unless a forced import is used.

## Common reasons an import shows "0 imported"

- **No term column recognised.** The most common case: the sheet's term is under
  a header the importer didn't match. Rename it to `Word` (vocab) or `Grammar`
  (grammar), or use one of the aliases above. The report now says this explicitly.
- **Picked the wrong kind.** A grammar sheet imported as "vocabulary" fails every
  row because vocabulary requires `Translation`. Switch the kind selector.
- **Missing Level.** Every row needs a level.

Download a starter template from the import page to see a known-good layout.
