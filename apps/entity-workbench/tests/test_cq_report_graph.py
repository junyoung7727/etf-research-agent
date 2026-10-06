import unittest
from paths import APP
from backend.view_design import read_catalog
from backend.puppygraph_schema import build_schema


class ReportGraphTests(unittest.TestCase):
    def test_published_reports_are_discoverable_from_etf_and_exclude_operational_runs(self):
        catalog=read_catalog()
        graph,_=build_schema(catalog,['ETF','ETFOutlookReport','ETFPriceExplanation'])
        self.assertEqual(len(graph['edge']),2)
        for view in ('etf_outlook_report','etf_price_explanation'):
            sql=(APP/'sql/views'/(view+'.sql')).read_text(encoding='utf8')
            for clause in ("a.status='completed'","a.data_source='database'",'a.published_at IS NOT NULL',"t.status='completed'"):
                self.assertIn(clause,sql)
            self.assertNotIn("t.status='succeeded'",sql)
        self.assertIn('a.withdrawn_at IS NULL',(APP/'sql/views/etf_price_explanation.sql').read_text(encoding='utf8'))
