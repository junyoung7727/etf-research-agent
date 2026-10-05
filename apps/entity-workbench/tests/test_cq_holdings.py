import tempfile
import unittest
from backend.cq_tools import CQTools
from tests.test_cq_graph import catalog


class HoldingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.tools=CQTools(lambda q,p:[],catalog(),self.tmp.name,'2026-10-05T00:00:00+00:00')

    def save(self,day,weights,etf='fund'):
        selection={'etf_ref':{'object_type':'ETF','object_id':etf},'selected_date':day,
            'items':[{'object_type':'Equity','object_id':key,'weight_ratio':value,'holding_id':key+day} for key,value in weights]}
        saved=self.tools.store.commit('fixture',{}, {'selection':selection},elapsed_ms=0,queries=[])
        return {'tool_run_id':saved['tool_run_id'],'path':'/selection'}

    def test_unknown_weight_is_not_zero_or_renormalized_and_prevents_top_ranking(self):
        ref=self.save('2026-10-02',[('a','0.2422'),('b','0.1656'),('c',None)])
        result,_=self.tools.holding_calculations.summarize(ref)
        self.assertEqual(result['items'][0]['weight_percent'],'40.7800')
        self.assertEqual(result['items'][0]['status'],'partial')
        with self.assertRaisesRegex(ValueError,'Unknown weights'):self.tools.holding_calculations.summarize(ref,top_n=2)
        result,_=self.tools.holding_calculations.summarize(ref,members=[{'object_type':'Equity','object_id':'a'}]*2)
        self.assertEqual(result['items'][0]['raw_weight_sum'],'0.2422')

    def test_date_comparison_preserves_missing_instead_of_inventing_zero_weight(self):
        a=self.save('2026-09-11',[('a','0.2468'),('b','0.10')]);b=self.save('2026-10-02',[('a','0.2422'),('c','0.20')])
        result,_=self.tools.holding_calculations.compare(a,b);rows={r['object_id']:r for r in result['items']}
        self.assertEqual(rows['a']['percentage_point_change'],'-0.4600')
        self.assertIsNone(rows['b']['weight_change']);self.assertFalse(rows['b']['later_present'])
        other=self.save('2026-10-02',[('a','0.2')],etf='other')
        with self.assertRaisesRegex(ValueError,'same ETF'):self.tools.holding_calculations.compare(a,other)
