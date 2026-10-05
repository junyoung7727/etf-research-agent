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

    def test_flow_sum_retains_its_actual_period_so_it_cannot_be_relabelled_as_a_price_window(self):
        data={'items':[{'object_id':'flow'+day,'properties':{'instrumentId':'fund','tradeDate':day,'netValForeign':value}}
            for day,value in [('2026-09-15','-600000000'),('2026-10-02','84000000')]],
            'selection':{'items':[{'object_id':'fund','object':{'properties':{'currencyCode':'KRW'}}}]},
            'scope':{'dataset_kind':'flow_observations','frequency':'daily','start_date':'2026-09-15','end_date':'2026-10-05'}}
        saved=self.tools.store.commit('fixture',{}, {},elapsed_ms=0,queries=[],dataset=data)
        result,_=self.tools.context.flow_totals(saved['result']['dataset_ref'],'netValForeign')
        row=result['items'][0]
        self.assertEqual(row['value_in_krw_100million'],'-5.16')
        self.assertEqual(row['requested_start_date'],'2026-09-15')
        self.assertEqual(row['last_observation_date'],'2026-10-02')
