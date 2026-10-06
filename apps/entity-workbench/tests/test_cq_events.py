import unittest
from types import SimpleNamespace
from datetime import date
from backend.cq_events import EventTools,feature_status


def measurement(value,**extra):
    return {'object_id':'measurement','properties':{'metricCode':'CONTRACT_VALUE','value':value,'unit':'KRW','periodBasis':'TOTAL',
        'valueSource':'PARSED','parseStatus':'ok','argumentGroup':1,**extra}}


CONDITION={'metric_code':'CONTRACT_VALUE','operator':'gte','value':'100','unit':'KRW','period_basis':'TOTAL'}


class EventFeatureTests(unittest.TestCase):
    def test_reported_date_is_not_advertised_as_verified_execution_date(self):
        schemas=[]
        EventTools(SimpleNamespace(graph=None,register=lambda *args:schemas.append(args)))
        date_input=schemas[0][2]['time_field']
        self.assertNotIn('occurred',date_input['enum'])
        event={'object_type':'SourceEvent','object_id':'e','title':'September filing',
            'properties':{'eventDate':'2026-09-23','lifecycleStage':'DEFINITIVE_SIGNED'}}
        shown=EventTools.display({'event':event,'participants':[],'features':[],'documents':[]})
        self.assertEqual(shown['event_date'],'2026-09-23')
        self.assertIn('not certified',shown['event_date_scope'])
        self.assertIn('not a verified current',shown['stage_scope'])

    def test_missing_invalid_units_and_approximate_values_are_unknown_not_zero(self):
        for rows in ([],[measurement(None)],[measurement('120',unit='USD')],
                     [measurement('120',periodBasis='UNKNOWN')],[measurement('120',parseStatus='approx_or_range')]):
            self.assertEqual(feature_status(rows,CONDITION),'unknown')

    def test_conflicting_values_are_not_resolved_by_repetition(self):
        self.assertEqual(feature_status([measurement('120')]*5+[measurement('80')],CONDITION),'unknown')
        self.assertEqual(feature_status([measurement('100')],CONDITION),'matched')
        self.assertEqual(feature_status([measurement('99.999999999999999999')],CONDITION),'not_matched')

    def test_role_in_one_group_and_amount_in_another_cannot_satisfy_combined_question(self):
        actor={'object_type':'Company','object_id':'a','title':'Company A'}
        event={'object_type':'SourceEvent','object_id':'e','title':'Event','properties':{}}
        graph=SimpleNamespace(query=lambda *a,**kw:[{'code':'CONTRACT_VALUE'}],
            linked=lambda refs,*a,**kw:[{'target':event}] if refs else [])
        owner=SimpleNamespace(graph=graph,register=lambda *a:None,check_date=date.fromisoformat,
            select=lambda _: {'items':[]},actors=lambda _:([{k:actor[k] for k in ('object_type','object_id')}],[]),
            result=lambda items,**kw:(items,kw))
        tool=EventTools(owner)
        tool.enrich=lambda _: [{'event':event,'participants':[{'actor':actor,'role':'SUPPLIER','argument_group':1}],
            'features':[measurement('200',argumentGroup=2)],'documents':[]}]
        result,_=tool.search({},'2026-10-01','2026-10-05','reported_event_date',
            participant_conditions=[{'role_codes':['SUPPLIER']}],feature_filters=[CONDITION])
        self.assertEqual(result[0]['match_status'],'unknown')

    def test_company_scope_does_not_accept_an_equity_as_participant_identity(self):
        actor={'object_type':'Company','object_id':'a'}
        event={'object_type':'SourceEvent','object_id':'e','properties':{}}
        graph=SimpleNamespace(linked=lambda refs,*a,**kw:[{'target':event}] if refs else [])
        owner=SimpleNamespace(graph=graph,register=lambda *a:None,check_date=date.fromisoformat,
            select=lambda _: {},actors=lambda _:([actor],[]),result=lambda *a,**kw:None)
        tool=EventTools(owner);tool.enrich=lambda _:[{'event':event,'participants':[],'features':[],'documents':[]}]
        with self.assertRaisesRegex(ValueError,'Actor'):
            tool.search({},'2026-10-01','2026-10-05','reported_event_date',participant_conditions=[{
                'role_codes':['SUPPLIER'],'actor_refs':[{'object_type':'Equity','object_id':'a'}]}])
