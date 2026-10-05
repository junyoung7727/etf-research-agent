import tempfile
import unittest
from backend.cq_tools import CQTools
from tests.test_cq_graph import catalog


class MarketCalculationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.tools=CQTools(lambda q,p:[],catalog(),self.tmp.name,'2026-10-05T23:00:00+00:00')

    def save(self,kind,items,selection):
        r=self.tools.store.commit('fixture',{}, {},elapsed_ms=0,queries=[],dataset={'scope':{'dataset_kind':kind},
            'items':items,'selection':{'items':selection}})
        return r['result']['dataset_ref']

    def member(self,id,weight=None,kind='Equity'):
        return {'object_type':kind,'object_id':id,'status':'resolved','weight_ratio':weight,
            'object':{'properties':{'currencyCode':'KRW'}}}

    def test_nav_change_uses_nav_endpoints_and_cannot_become_price_breadth(self):
        rows=[{'object_type':kind,'object_id':kind+day,'properties':{
            'tradeDate':day,('etfInstrumentId' if kind=='DailyNAV' else 'instrumentId'):'fund',
            ('nav' if kind=='DailyNAV' else 'closePrice'):value}}
            for kind,day,value in [('DailyNAV','2026-10-01','100'),('DailyNAV','2026-10-02','110'),
                ('DailyBar','2026-10-01','90'),('DailyBar','2026-10-02','99')]]
        ref=self.save('price_observations',rows,[self.member('fund',kind='ETF')])
        response=self.tools.call('calculate_returns',{'dataset_ref':ref,'start_date':'2026-10-01',
            'end_date':'2026-10-02','price_field':'nav'})
        item=response['result']['items'][0]
        self.assertEqual(item['return_ratio'],'0.1')
        self.assertEqual(item['input_ids'],['DailyNAV2026-10-01','DailyNAV2026-10-02'])
        self.assertIn('not market-price or total return',item['interpretation'])
        with self.assertRaisesRegex(ValueError,'NAV'):
            self.tools.market.breadth(response['result']['dataset_ref'])
        missing,_=self.tools.market.returns(ref,'2026-09-30','2026-10-02','nav')
        self.assertEqual(missing['items'][0]['status'],'unavailable')

    def test_intraday_rows_carry_unknown_aggregation_basis_to_prevent_daily_total_inference(self):
        items=[{'properties':{'instrumentId':'a','tradeDate':'2026-10-02','netQtyForeign':120}}]
        self.tools.market.observations=lambda *args:(items,{'items':[self.member('a')]},{})
        result,_=self.tools.market.flows({},'2026-10-02','2026-10-02','intraday')
        self.assertIn('neither cumulative nor incremental',result['items'][0]['aggregation_basis'])
        self.assertEqual(result['items'][0]['properties']['netQtyForeign'],120)

    def test_breadth_preserves_large_down_weight_and_missing_not_flat(self):
        items=[{'object_id':str(i),'status':'calculated','return_ratio':'0.01','weight_ratio':0.02} for i in range(9)]
        items+=[{'object_id':'large','status':'calculated','return_ratio':'-0.02','weight_ratio':0.75},
                {'object_id':'missing','status':'unavailable','return_ratio':None,'weight_ratio':None}]
        ref=self.save('returns',items,[])
        result,_=self.tools.market.breadth(ref)
        rows={r['direction']:r for r in result['items']}
        self.assertEqual(rows['up']['count'],9);self.assertEqual(rows['up']['raw_weight_sum'],'0.18')
        self.assertEqual(rows['down']['raw_weight_sum'],'0.75')
        self.assertEqual(rows['unavailable']['count'],1);self.assertEqual(rows['flat']['count'],0)

    def test_returns_do_not_substitute_nearby_date_or_guess_unknown_basis(self):
        prices=[{'object_type':'DailyBar','object_id':'p'+str(i),'properties':{
            'instrumentId':'a','tradeDate':day,'closePrice':str(value),'priceBasis':None}} for i,(day,value) in enumerate([
            ('2026-10-01',100),('2026-10-02',110)])]
        ref=self.save('price_observations',prices,[self.member('a')])
        result,_=self.tools.market.returns(ref,'2026-10-01','2026-10-02','closePrice')
        self.assertIsNone(result['items'][0]['return_ratio'])
        self.assertEqual(result['items'][0]['reason'],'unknown_or_mismatched_price_basis')
        result,_=self.tools.market.returns(ref,'2026-10-01','2026-10-02','closePrice','observed_close_only')
        self.assertEqual(result['items'][0]['return_ratio'],'0.1')
        self.assertIn('not certified',result['items'][0]['interpretation'])
        result,_=self.tools.market.returns(ref,'2026-09-30','2026-10-02','closePrice')
        self.assertEqual(result['items'][0]['reason'],'missing_or_ambiguous_exact_endpoint')

    def test_nav_requires_exact_date_and_positive_per_unit_value(self):
        rows=[{'object_type':'DailyBar','object_id':'p','properties':{'instrumentId':'fund','tradeDate':'2026-10-02','closePrice':'105'}},
              {'object_type':'DailyNAV','object_id':'n','properties':{'etfInstrumentId':'fund','tradeDate':'2026-10-02','nav':'100'}}]
        ref=self.save('price_observations',rows,[self.member('fund',kind='ETF')])
        result,_=self.tools.market.nav(ref,'2026-10-02')
        self.assertEqual(result['items'][0]['premium_ratio'],'0.05')
        result,_=self.tools.market.nav(ref,'2026-10-01')
        self.assertIsNone(result['items'][0]['premium_ratio'])
        rows[1]['properties']['nav']='0';ref=self.save('price_observations',rows,[self.member('fund',kind='ETF')])
        result,_=self.tools.market.nav(ref,'2026-10-02');self.assertIsNone(result['items'][0]['premium_ratio'])
