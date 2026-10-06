# Versioned CQ benchmark

1. Register one agent release for changes to tracked app code, tools, skills, model definitions, SQL views and prompts. A source checksum catches edits before execution; CI checks the base revision and requires a strictly increasing release. External harness, graph catalog and model settings are recorded in the execution identity so changed dependencies cannot share a comparison bucket.
2. Save the release and evaluation contract with local and cloud executions. Preserve unknown versions and historical evidence. Build a 13-row matrix per execution version; select the latest canonical run per CQ, including failures, without substituting another version's results. Unexecuted is distinct from unevaluated and failed.
3. Add the version selector and whole-CQ table above CQ detail. Link rows to that exact run, preserve version selection through navigation, and retain the four grouped quality columns plus technical status and execution status.

Validation: source changes/deletions/new files require bump; unchanged or docs-only changes do not. CI rejects reused/decreased releases. External runtime changes alter execution identity. Matrix isolation, latest failure selection, missing cases, frozen contracts, deep links and mobile overflow have automated coverage. No live model run or cloud deployment is required for implementation verification.

Limits: repository CI supplies a failing check; requiring it for merge is a repository branch-protection setting. Unmanaged external database DDL cannot be detected from Git; graph catalog and checked-in SQL are versioned, and runtime dependencies are recorded separately.
