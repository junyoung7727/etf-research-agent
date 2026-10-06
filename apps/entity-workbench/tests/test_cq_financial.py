import tempfile
import unittest
from backend.cq_tools import CQTools
from tests.test_cq_graph import catalog


class FinancialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.tools=CQTools(lambda q,p:[],catalog(),self.tmp.name,'2026-10-05T00:00:00+00:00')

    def save(self,items,kind='financial_observations'):
        return self.tools.store.commit('fixture',{}, {},elapsed_ms=0,queries=[],dataset={
            'items':items,'selection':None,'scope':{'dataset_kind':kind}})['result']['dataset_ref']

    def obs(self,id,value,**kwargs):
        return {'object_type':'FinancialMetric','object_id':id,'properties':{
            'corpCode':'c','metric':'revenue','unit':'KRW','currencyCode':'KRW','fsBasis':'CFS',
            'fiscalYear':2026,'fiscalPeriod':'Q2','periodKind':'QUARTER','derivation':'reported',
            'periodEnd':'2026-06-30','availableAt':'2026-08-01T00:00:00+00:00','value':value,**kwargs}}

    def test_cross_company_and_accounting_basis_cannot_create_growth_rate(self):
        first=self.obs('a','100',periodEnd='2026-03-31',fiscalPeriod='Q1')
        for change in ({'corpCode':'other'},{'fsBasis':'OFS'},{'periodKind':'YTD'},{'unit':'USD'}):
            ref=self.save([first,self.obs('b','200',**change)])
            with self.assertRaisesRegex(ValueError,'dimension'):self.tools.financial.compare(ref,'a','b')

    def test_negative_base_has_difference_but_no_misleading_growth_percentage(self):
        ref=self.save([self.obs('a','-100',periodEnd='2026-03-31'),self.obs('b','50')])
        result,_=self.tools.financial.compare(ref,'a','b')
        self.assertEqual(result['items'][0]['difference'],'150')
        self.assertIsNone(result['items'][0]['change_ratio'])

    def test_cumulative_growth_requires_equal_period_lengths(self):
        ref=self.save([self.obs('a','100',periodEnd='2026-03-31',fiscalPeriod='Q1',periodKind='CUMULATIVE'),
                       self.obs('b','200',periodKind='CUMULATIVE')])
        with self.assertRaisesRegex(ValueError,'fiscalPeriod'):self.tools.financial.compare(ref,'a','b')
        ref=self.save([self.obs('a','100',periodEnd='2025-06-30',fiscalYear=2025,periodKind='CUMULATIVE'),
                       self.obs('b','200',periodKind='CUMULATIVE')])
        result,_=self.tools.financial.compare(ref,'a','b')
        self.assertEqual(result['items'][0]['change_ratio'],'1')

    def test_eps_and_unmatched_revision_are_not_derived_as_fourth_quarter(self):
        for metric in ('EPS','revenue'):
            ref=self.save([self.obs('a','100',metric=metric,fiscalPeriod='FY',periodKind='YTD',rceptNo='r1'),
                self.obs('b','60',metric=metric,fiscalPeriod='Q3',periodKind='YTD',rceptNo='r2')])
            with self.assertRaises(ValueError):self.tools.financial.derive(ref,'a','b')

    def test_later_expectation_and_untyped_news_value_are_rejected(self):
        actual=self.save([self.obs('actual','120')])
        expected=self.save([self.obs('estimate','100',availableAt='2026-08-02T00:00:00+00:00')],'expected_financial_observations')
        with self.assertRaisesRegex(ValueError,'before'):self.tools.financial.expectation(actual,'actual',expected,'estimate')
        expected=self.save([self.obs('estimate','100')],'guidance_events')
        with self.assertRaisesRegex(ValueError,'consensus'):self.tools.financial.expectation(actual,'actual',expected,'estimate')
