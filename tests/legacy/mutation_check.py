"""Targeted test-sensitivity checks; mutate in memory, never production files.

Run from the repository root: python tests/legacy/mutation_check.py
These plausible regressions must be detected; this is not exhaustive mutation testing.
"""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from tools import check_workspace, render_scan, score


MUTATIONS = [
    (score, "missing value charged as zero", "/ cov if cov else None", "/ 100 if cov else None"),
    (score, "macro default silently changed", 'horizon="swing", macro=50', 'horizon="swing", macro=0'),
    (score, "volume bands collapsed", "r > 1.3", "r > 10"),
    (check_workspace, "coverage gate weakened", "cov < 60", "cov < 50"),
    (check_workspace, "missing fund weight tolerated", "abs(total - 100) > TOL", "False"),
    (render_scan, "report date replaced", "{e(r['date'])}", "2099-01-01"),
    (score, "trend stuck bullish", "def score_trend(t):", "def score_trend(t):\n    return 100"),
    (score, "momentum stuck bullish", "def score_momentum(t):", "def score_momentum(t):\n    return 100"),
    (score, "position stuck at zero", "def score_position(t, horizon):", "def score_position(t, horizon):\n    return 0"),
    (score, "relative strength stuck bullish", "def score_rs(t):", "def score_rs(t):\n    return 100"),
    (score, "long weights swapped", '"trend": 15, "momentum": 5', '"trend": 5, "momentum": 15'),
    (score, "positive valuation dropped", "if pe < 0:", "if pe >= 0:\n        return None\n    if pe < 0:"),
]


def run_tests():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"),
                                               top_level_dir=str(ROOT / "tests"))
    return unittest.TextTestRunner(stream=io.StringIO()).run(suite)


def main():
    baseline = run_tests()
    if not baseline.wasSuccessful() or baseline.testsRun == 0 or baseline.skipped:
        raise SystemExit("Baseline must pass without skips before testing mutations")
    for module, label, before, after in MUTATIONS:
        source = Path(module.__file__).read_text(encoding="utf-8")
        if source.count(before) != 1:
            raise SystemExit("Mutation target changed: " + label)
        try:
            exec(compile(source.replace(before, after), module.__file__, "exec"), module.__dict__)
            result = run_tests()
            if result.errors or result.skipped or not result.failures:
                raise SystemExit("Mutation not caught by an assertion: " + label)
            print("caught:", label)
        finally:
            exec(compile(source, module.__file__, "exec"), module.__dict__)
    restored = run_tests()
    if not restored.wasSuccessful() or restored.skipped:
        raise SystemExit("Restored baseline failed")
    print(f"ok: {len(MUTATIONS)}/{len(MUTATIONS)} mutations caught; restored baseline passed")


if __name__ == "__main__":
    main()
