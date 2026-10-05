# Library definitions and dashboard drafts

The default read combines two sources. The library owns applied definitions;
the dashboard owns only unpublished definitions and changed fields.

```text
EDGE_ONTOLOGY_ROOT / metadata, rules ─┐
                                    ├─ merged read → dashboard
dashboard object/link YAML + deltas ─┘
                 │
       Apply to library (explicit button)
                 ↓
       validate → write → read back → remove applied draft
```

- Library path: `data/library.json`, overridden by `EDGE_ONTOLOGY_ROOT`.
- Object/Link drafts: `ontology/metadata/object_types` and `link_types`.
- Value Type drafts: current sparse delta in `output/entity-workbench/value-types.sqlite3`.
- Object display cache: `models.sqlite3`. This is generated from both sources, not an editable schema source.
- Original PostgreSQL source mappings and domain definitions are preserved.

Object/Link apply moves all pending YAML files together after combined validation.
Cross-source links are resolved before promotion. Different definitions for the same
ID fail explicitly; identical files may be deduplicated. The graph after moving must
be the same as the graph before moving.

Value Type apply writes event descriptions, families and identity rules into their
existing native library YAML. Event properties, roles and other fields are preserved.
Additional enum definitions/annotations live in `metadata/value_types/enum_annotations.yaml`;
they contain only information absent from native definitions. The reader unions them
with the native catalog. This does not install validation into downstream ingestion.
A newly added event code with no native role/property schema stays a draft; apply
fails with its code rather than inventing a schema. Save and apply are separate actions.

Source hashes and draft revisions reject stale requests. An empty delta never pins
the reader to an old library version. Failed writes/read-back restore touched files
and preserve drafts. Individual files use atomic replacement; the multi-file batch
is not a database transaction across process termination. Do not run a second writer
against these paths during apply. Library file application never invokes Git, deploys
the library, changes database rows or reconnects event threads.

Verification: split-source links, identity conflicts, stale edits, rollback, sparse
storage, native-schema preservation, independent library reads after apply, and browser
save/apply/reload using an isolated copy of the library.
