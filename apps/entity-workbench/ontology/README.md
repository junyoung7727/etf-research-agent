# Portable ontology definitions

```text
metadata/
  object_types/     # one object, properties and original source mapping per YAML
  link_types/       # one directed Link Type per YAML; objects reference its ID
  value_types/      # reserved; current values are read from EDGE, drafts live in output/
rules/
  threading/       # reserved; current rules are read from EDGE, not copied here
oms/
  loader.py        # YAML parsing and reference resolution only
```

This directory contains unpublished Object/Link definitions only. The reader combines it with library metadata using `read_definitions(directory, library)`. Explicit application moves validated files into the library and removes the drafts. The reader has no dependency on HTTP, SQLite, source database snapshots or frontend code.

Object definitions reference Link Types using `linkTypes: [Company_Issues_Equity, ...]`. Each link file stores its ID, source object and original definition. Reference ownership, duplication and unused link files are checked. Source mappings retain their original PostgreSQL paths.

Value Type edits are stored as a sparse local delta. Explicit application updates native library YAML and clears that delta. No Git commit is created. `EDGE_ONTOLOGY_ROOT` selects the external library package directory; the reader supports both its previous `resources` layout and the reorganized `metadata` / `rules` layout. Unchanged definitions retain the same source fingerprint across the move.
