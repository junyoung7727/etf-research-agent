"""Keep missing coverage, missing weight, and report values visible."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import check_workspace, render_scan


def envelope(payload):
    return {"artifact": "synthetic regression fixture", "as_of_date": "2026-09-04",
            "generated_by": "test", "sources": [{"source_name": "synthetic"}],
            "source_conflicts": [], "confidence": "high", "coverage": {},
            "payload": payload}


class WorkspaceRegression(unittest.TestCase):
    def failures(self, name, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / name
            path.write_text(json.dumps(data), encoding="ascii")
            return list(check_workspace.check(path))

    def test_non_theme_weight_cannot_disappear(self):
        data = envelope({"chains": [
            {"chain": "theme", "weight_pct": 60, "holdings": [{"weight_pct": 60}]},
            {"chain": "non-theme: cash", "weight_pct": 40, "holdings": []}],
            "unclassified_pct": 0, "purity_pct": 60})
        self.assertEqual(self.failures("07_valuechain_ETF.json", data), [])
        data["payload"]["chains"].pop()
        self.assertTrue(any("40.00% of the fund is unaccounted for" in f
                            for f in self.failures("07_valuechain_ETF.json", data)))

    def test_declared_holdings_and_purity_must_reconcile(self):
        data = envelope({"chains": [{"chain": "theme", "weight_pct": 100,
                                    "holdings": [{"weight_pct": 60}]}],
                         "unclassified_pct": 0, "purity_pct": 60})
        errors = self.failures("07_valuechain_ETF.json", data)
        self.assertTrue(any("holdings sum to 60.00%" in f for f in errors))
        self.assertTrue(any("purity_pct" in f for f in errors))

    def test_coverage_gate_boundary_for_all_three_grading_artifacts(self):
        for prefix in ("08", "09", "10"):
            for coverage, grade, valid in [(59.9, "B", False), (59.9, None, True),
                                           (60, "B", True)]:
                with self.subTest(prefix=prefix, coverage=coverage, grade=grade):
                    data = envelope({"coverage_pct": coverage, "final_grade": grade})
                    self.assertEqual(not self.failures(prefix + "_grade.json", data), valid)

    def test_sources_and_rationale_remain_required(self):
        data = envelope({"items": [{"name": "ETF", "grade": "B"}]})
        data["sources"] = []
        del data["as_of_date"]
        errors = self.failures("08_grade.json", data)
        self.assertTrue(any("sources is empty" in f for f in errors))
        self.assertTrue(any("envelope missing 'as_of_date'" in f for f in errors))
        self.assertTrue(any("no rationale" in f for f in errors))

    def test_script_bookkeeping_does_not_acquire_agent_envelope(self):
        for name in ("12b_signal_scores.json", "agent_costs.json"):
            with self.subTest(name=name):
                self.assertEqual(self.failures(name, {"ETF": {}}), [])


# Small synthetic scan, not an investment conclusion or a production data sample.
SCAN = {"swing": 73.7, "long": 58.8, "short": 77.5, "close": 300, "chg": 0.33,
        "date": "2026-09-04", "macro": 50, "d20": 7.14, "rs": 7.14,
        "pos60": 96.83, "fh": -0.66, "vol": 2, "breadth": "1/2",
        "parts": {"macro": 50, "value": None, "trend": 100, "momentum": 100,
                  "position": 0, "rs": 100, "flow": 100},
        "weights": {"macro": 10, "value": 5, "trend": 25, "momentum": 20,
                    "position": 20, "rs": 15, "flow": 5},
        "holdings": [{"sym": "AAA", "w": 60, "score": 90},
                     {"sym": "BBB", "w": 40, "score": 10}]}
META = {"names": {"ETF": "ETF <synthetic>"}, "sectors": {"ETF": "test & only"}}
GATE = {"status": "conditional", "reasons": ["synthetic <risk>"]}


class RenderRegression(unittest.TestCase):
    def test_report_copies_values_discloses_gaps_and_escapes_text(self):
        page = render_scan.page("ETF", SCAN, GATE, META)
        for text in ("73.7", "long 58.8", "short 77.5", "n/a", "wt 5%",
                     "1/2", "60.00%", "40.00%", "2026-09-04", "macro input 50",
                     "ETF &lt;synthetic&gt;", "synthetic &lt;risk&gt;", "conditional"):
            with self.subTest(text=text):
                self.assertIn(text, page)
        self.assertNotIn("ETF <synthetic>", page)
        self.assertEqual(page, render_scan.page("ETF", copy.deepcopy(SCAN), GATE, META))
        # Reviewed legacy HTML baseline; no dates or financial numbers stripped.
        self.assertEqual(hashlib.sha256(page.encode("utf-8")).hexdigest(),
                         "01d2e543175ef74728bc1b80bcd6c9998caaac6f7d8c64561bdab0eea072ef17")

    def test_treemap_conserves_area_and_holding_identity(self):
        tiles = render_scan.squarify([(60, "AAA"), (40, "BBB")], 0, 0, 100, 100)
        self.assertEqual([symbol for _, symbol in tiles], ["AAA", "BBB"])
        self.assertEqual([w * h for (_, _, w, h), _ in tiles], [6000, 4000])
