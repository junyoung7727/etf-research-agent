import tempfile
import unittest
from backend.cq_tools import CQTools
from tests.test_cq_graph import catalog


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.tools=CQTools(lambda q,p:[],catalog(),self.tmp.name,'2026-10-05T00:00:00+00:00')

    def selection(self,weights):
        selection={'etf_ref':{},'selected_date':'2026-10-02','items':[
            {'object_type':'Equity','object_id':key,'weight_ratio':weight,'status':'resolved'} for key,weight in weights]}
        r=self.tools.store.commit('fixture',{}, {'selection':selection},elapsed_ms=0,queries=[])
        return {'tool_run_id':r['tool_run_id'],'path':'/selection'}

    def test_exposure_uses_raw_weight_minimum_without_renormalizing_missing_assets(self):
        left=self.selection([('a',0.2),('b',0.4),('unknown',None)])
        right=self.selection([('a',0.5),('c',0.3)])
        result,_=self.tools.context.exposure(left,right,'security')
        self.assertEqual(result['data_scope']['overlap_weight'],'0.2')
        self.assertEqual(result['data_scope']['unresolved_left'],['unknown'])

    def test_company_overlap_uses_declared_issuer_edges_and_preserves_two_share_classes(self):
        self.tools.actors=lambda selection: ([],[{'security':{'object_id':r['object_id']},'actor':{'object_id':'issuer'}} for r in selection['items']])
        left=self.selection([('common',0.2),('preferred',0.3)])
        right=self.selection([('common',0.4)])
        result,_=self.tools.context.exposure(left,right,'company')
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['left_weight'],'0.5')
        self.assertEqual(result['data_scope']['overlap_weight'],'0.4')
