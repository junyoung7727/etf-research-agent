"""Freeze legacy scoring behavior, not a policy for the new outlook path."""
import contextlib
import datetime
import io
import unittest
from unittest.mock import patch

from tools import score


def prices(symbol, days):
    # Synthetic newest-first weekday bars: ETF rises 1 per session; SPY is flat.
    rows = []
    date = datetime.date(2026, 9, 4)
    while len(rows) < days:
        if date.weekday() < 5:
            i = len(rows)
            close = 100 if symbol == "SPY" else 300 - i
            rows.append({"date": date.isoformat(), "close": close,
                         "high": close + 2, "low": close - 2,
                         "volume": 200 if i < 20 else 100})
        date -= datetime.timedelta(days=1)
    return rows


class ScoreRegression(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.network = stack.enter_context(patch("urllib.request.urlopen",
                                                side_effect=AssertionError("live HTTP forbidden")))
        stack.enter_context(patch.object(score.data, "prices", side_effect=prices))
        self.ratios = stack.enter_context(patch.object(score.data, "ratios", return_value={}))

    def tearDown(self):
        # Even a swallowed provider exception must not hide a live request.
        self.network.assert_not_called()

    def test_missing_value_keeps_gap_and_renormalises_each_horizon(self):
        expected = {"long": (5000 / 85, 85), "swing": (7000 / 95, 95),
                    "short": (77.5, 100)}
        for horizon, (total, coverage) in expected.items():
            with self.subTest(horizon=horizon):
                actual, parts, weights, _, cov = score.score("ETF", horizon)
                self.assertAlmostEqual(actual, total)
                self.assertEqual(cov, coverage)
                self.assertEqual(sum(weights.values()), 100)
                self.assertEqual(parts, {"macro": 50, "value": None, "trend": 100,
                                        "momentum": 100, "position": 0,
                                        "rs": 100, "flow": 100})

    def test_price_windows_and_benchmark_units_are_preserved(self):
        t = score.technicals("ETF", bench_20d=2)
        self.assertEqual(t["date"], "2026-09-04")
        expected = {"close": 300, "ma20": 290.5, "ma60": 270.5,
                    "ma200": 200.5, "d20": 100 / 14, "rs": 100 / 14 - 2,
                    "chg": 100 / 299, "pos60": 6100 / 63,
                    "range_all": 100, "from_high": -200 / 302, "vol_ratio": 2}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertAlmostEqual(t[key], value)

    def test_each_horizon_keeps_its_weight_profile(self):
        self.assertEqual(score.WEIGHTS, {
            "long": {"macro": 40, "value": 15, "trend": 15, "momentum": 5,
                     "position": 15, "rs": 5, "flow": 5},
            "swing": {"macro": 10, "value": 5, "trend": 25, "momentum": 20,
                      "position": 20, "rs": 15, "flow": 5},
            "short": {"macro": 5, "value": 0, "trend": 25, "momentum": 25,
                      "position": 20, "rs": 15, "flow": 10}})

    def test_declining_and_mixed_states_are_not_constant_bullish_scores(self):
        cases = [
            ({"ma20": 110, "ma60": 100, "close": 105, "ma200": 100,
              "from_high": -5, "d20": -1, "vol_ratio": 1.5, "rs": -6,
              "pos60": 40, "range_all": 40}, (75, 0, 0, 75, 62.5)),
            ({"ma20": 90, "ma60": 100, "close": 80, "ma200": 100,
              "from_high": -35, "d20": -5, "vol_ratio": 0.8, "rs": 3,
              "pos60": 20, "range_all": 20}, (0, 40, 75, 100, 100)),
            ({"ma20": 90, "ma60": 100, "close": 95, "ma200": 100,
              "from_high": -10, "d20": 2, "vol_ratio": 1, "rs": 0,
              "pos60": 55, "range_all": 60}, (25, 75, 50, 50, 62.5)),
        ]
        for t, expected in cases:
            with self.subTest(state=t):
                actual = (score.score_trend(t), score.score_momentum(t), score.score_rs(t),
                          score.score_position(t, "swing"), score.score_position(t, "long"))
                self.assertEqual(actual, expected)

    def test_positive_pe_contributes_instead_of_becoming_missing(self):
        for sector, pe, expected in [(None, 20, 75), (None, 70, 25),
                                     ("fabless", 10, 100), ("foundry", 26, 50),
                                     ("fabless", 50, 25), ("memory", 31, 0)]:
            with self.subTest(sector=sector, pe=pe):
                self.ratios.return_value = {"priceToEarningsRatioTTM": pe}
                self.assertEqual(score.score_value("ETF", sector), expected)
        self.ratios.return_value = {"priceToEarningsRatioTTM": 20}
        total, parts, _, _, cov = score.score("ETF", "long")
        self.assertEqual((total, parts["value"], cov), (61.25, 75, 100))

    def test_lossmaking_is_not_missing_and_miner_keeps_legacy_placeholder(self):
        self.ratios.return_value = {"priceToEarningsRatioTTM": -1}
        total, parts, _, _, cov = score.score("ETF", "long")
        self.assertEqual((total, parts["value"], cov), (50, 0, 100))
        self.ratios.reset_mock()
        self.assertEqual(score.score_value("ETF", "miner"), 50)
        self.ratios.assert_not_called()

    def test_provider_failure_stays_missing(self):
        self.ratios.side_effect = RuntimeError("offline provider failure")
        self.assertIsNone(score.score("ETF")[1]["value"])

    def test_61_session_minimum_and_short_history_average(self):
        with self.assertRaisesRegex(ValueError, "need 61"):
            score.technicals("ETF", 0, days=60)
        self.assertEqual(score.technicals("ETF", 0, days=61)["ma200"], 270)

    def test_volume_proxy_retains_all_five_bands_and_boundaries(self):
        for ratio, expected in [(0.65, 0), (0.6501, 25), (0.85, 25),
                                (0.8501, 50), (1.05, 50), (1.0501, 75),
                                (1.3, 75), (1.3001, 100)]:
            with self.subTest(ratio=ratio):
                self.assertEqual(score.score_flow({"vol_ratio": ratio}), expected)

    def test_cli_discloses_missing_value_and_fixed_date(self):
        output = io.StringIO()
        with patch("sys.argv", ["score.py", "ETF"]), contextlib.redirect_stdout(output):
            score.main()
        text = output.getvalue()
        self.assertIn("ETF  2026-09-04  300.00 (+0.33%)", text)
        self.assertIn("swing score 73.7/100  (95% of weight has data)", text)
        self.assertIn("n/a  (weight  5%) -> excluded, renormalised", text)

    def test_cli_suspends_below_60_percent_instead_of_showing_total(self):
        result = score.score("ETF", "long", macro=None)
        self.assertEqual(result[-1], 45)
        output = io.StringIO()
        with patch.object(score, "score", return_value=result), \
                patch("sys.argv", ["score.py", "ETF", "--horizon", "long"]), \
                contextlib.redirect_stdout(output):
            score.main()
        self.assertIn("score suspended", output.getvalue())
        self.assertNotIn("/100", output.getvalue())
