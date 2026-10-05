import unittest
from backend.puppygraph_viewer import search,connections
from backend.view_design import read_catalog


class PuppyGraphViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.design=read_catalog()

    def test_all_connections_queries_every_implemented_link_without_date_filter(self):
        calls=[]
        def run(query,params):calls.append((query,params));return []
        result=connections(run=run,design=self.design)
        expected=[r for r in self.design['relations'] if r['physicalMapping']['kind']!='blocked']
        self.assertEqual(len(calls),len(expected))
        self.assertTrue(result['complete'])
        self.assertTrue(all('date(' not in query and not params for query,params in calls))

    def test_focus_includes_every_incident_direction_and_paginates_without_losing_roles(self):
        link=next(r for r in self.design['relations'] if r['id']=='Company_ParticipatesIn_SourceEvent')
        design={**self.design,'relations':[link]};calls=[]
        def run(query,params):
            calls.append(query)
            start=20 if 'SKIP 20' in query else 0
            return [{'sourceId':'company','targetId':'event','source':{'name':'A'},'target':{},
                     'key0':str(i),'prop_roleCode':'ROLE'+str(i),'prop_mentionedName':'A',
                     'prop_argumentGroup':i} for i in range(start,22)][:21]
        first=connections('SourceEvent','event',run=run,design=design)
        second=connections('SourceEvent','event',first['cursor'],run=run,design=design)
        self.assertFalse(first['complete']);self.assertTrue(second['complete'])
        self.assertEqual(len({e['key'] for e in first['edges']+second['edges']}),22)
        self.assertTrue(all('b.id=$id' in q for q in calls))
        self.assertTrue(all(e['source']=='["Company","company"]' for e in second['edges']))
        self.assertEqual({e['properties']['argumentGroup'] for e in first['edges']+second['edges']},set(range(22)))
        with self.assertRaises(ValueError):connections('SourceEvent','other',first['cursor'],run=run,design=design)

    def test_focus_self_links_match_both_directions(self):
        link=next(r for r in self.design['relations'] if r['source']==r['target'] and r['physicalMapping']['kind']!='blocked')
        calls=[]
        def run(query,params):calls.append(query);return []
        connections(link['source'],'id',run=run,design={**self.design,'relations':[link]})
        self.assertIn('(a.id=$id OR b.id=$id)',calls[0])

    def test_daily_history_continues_across_securities_without_a_date_cutoff(self):
        link=next(r for r in self.design['relations'] if r['id']=='DailyBar_ForSecurity_Equity')
        design={**self.design,'relations':[link]};calls=[]
        def run(query,params):
            calls.append((query,params))
            if query.startswith('MATCH (n:'):
                return [] if 'SKIP 1' in query else [{'id':'security'}]
            self.assertEqual(params['instrument'],'security')
            self.assertIn('a.instrumentId=$instrument',query)
            self.assertNotIn('date(',query)
            return [{'sourceId':'bar','targetId':'security','source':{'close':'12345678901234567890.123'},'target':{},'key0':'bar'}]
        first=connections(run=run,design=design)
        self.assertFalse(first['complete'])
        self.assertEqual(first['nodes'][0]['properties']['close'],'12345678901234567890.123')
        second=connections(cursor=first['cursor'],run=run,design=design)
        self.assertTrue(second['complete'])
        self.assertEqual(len(calls),3)

    def test_search_parameters_cannot_turn_into_cypher(self):
        calls=[]
        def run(query,params):calls.append((query,params));return []
        text="x' DELETE n //"
        self.assertEqual(search('Company',text,run)['nodes'],[])
        self.assertNotIn(text,calls[0][0]);self.assertEqual(calls[0][1]['q'],text)
        with self.assertRaises(ValueError):search('Company`) DELETE n',run=run)

    def test_etf_focus_queries_all_incident_relations_and_no_others(self):
        calls=[]
        def run(query,params):calls.append((query,params));return []
        result=connections('ETF','etf-id',run=run,design=self.design)
        incident=[r for r in self.design['relations'] if 'ETF' in (r['source'],r['target']) and r['physicalMapping']['kind']!='blocked']
        self.assertEqual(len(calls),len(incident))
        self.assertTrue(result['complete'])
        for query,params in calls:
            self.assertEqual(params['id'],'etf-id')
            self.assertNotIn('date(',query)
            self.assertTrue('a.id=$id' in query or 'b.id=$id' in query)
        self.assertTrue(any('a.id=$id' in query for query,_ in calls))
        self.assertTrue(any('b.id=$id' in query for query,_ in calls))

    def test_invalid_scope_and_stale_mapping_never_query(self):
        def run(*args):self.fail('Invalid request reached cloud')
        for args in [dict(kind='BadLabel',identifier='id'),dict(identifier='id'),dict(cursor='[]'),dict(cursor='null')]:
            with self.assertRaises(ValueError):connections(**args,run=run,design=self.design)
        with self.assertRaises(ValueError):connections(run=run,design={**self.design,'modelChanged':True})
