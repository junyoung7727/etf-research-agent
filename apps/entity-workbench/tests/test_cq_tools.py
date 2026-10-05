import tempfile
import unittest
from backend.cq_tools import CQTools
from tests.test_cq_graph import catalog


class CQToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.calls=[]
        def run(q,p):
            self.calls.append((q,p))
            return [{'id':str(i),'properties':{'name':'Company '+str(i)}} for i in range(3)]
        self.tools=CQTools(run,catalog(),self.tmp.name,'2026-10-05T00:00:00+00:00')

    def test_public_page_and_stored_full_dataset_are_separate(self):
        output=self.tools.call('search_objects',{'object_type':'Company','limit':1})
        self.assertEqual(len(output['result']['items']),1)
        self.assertNotIn('dataset',output['result'])
        ref=output['result']['dataset_ref']
        self.assertEqual(len(self.tools.store.reference(ref,'dataset')['items']),3)
        page=self.tools.call('get_result_page',{'dataset_ref':ref,'offset':1,'limit':2})
        self.assertEqual(len(page['result']['items']),2)
        self.assertTrue(page['result']['page']['complete'])
        self.assertEqual(len(self.calls),1)

    def test_unknown_filter_is_audited_as_error_not_empty_success(self):
        result=self.tools.call('search_objects',{'object_type':'Company','filters':{'unknown':'x'}})
        self.assertEqual(result['result']['status'],'invalid_or_unavailable')
        self.assertNotIn('dataset_ref',result['result'])
        self.assertEqual(len(self.calls),0)

    def test_future_holdings_date_is_rejected_before_graph_reads(self):
        result=self.tools.call('get_etf_holdings',{'etf_ref':{'object_type':'ETF','object_id':'x'},
            'holdings_date':'2026-10-06','date_policy':'exact'})
        self.assertEqual(result['result']['status'],'invalid_or_unavailable')
        self.assertEqual(len(self.calls),0)
