# Legacy compatibility baseline (PR 01)

Run from the repository root with Python 3.9+; no packages or API keys needed:

```sh
python -m unittest discover -s tests -v
python tests/legacy/mutation_check.py
python tools/score.py --self-check
python tools/validate.py --self-check
python tools/check_workspace.py --self-check
python tools/render_scan.py --self-check
```

The synthetic newest-first weekday bars, fixed scan, and malformed artifacts
freeze the existing path before adding opt-in outlook analysis. Provider calls
are replaced only inside tests; any HTTP attempt fails the scoring test.

These tests preserve legacy choices (macro default 50, miner valuation 50,
short-history moving averages, volume as a flow proxy). They do not endorse
those choices for the new outlook path or establish forecasting performance.

The scan hash protects exact UTF-8 page output including dates and numbers;
explicit value, escaping, and area assertions explain the important semantics.
Change the hash only after reviewing an intentional renderer change. Network
integration, visual browser layout, and LLM instruction quality are not tested.
