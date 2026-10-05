import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from backend.server import browse, save_review, read_reviews, fingerprint, matches_fk, entity_catalog, row_connections


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'snapshot.sqlite3'
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('CREATE TABLE entity(entity_id TEXT PRIMARY KEY, display_name TEXT, entity_type TEXT)')
            c.executemany('INSERT INTO entity VALUES(?,?,?)', [('a','삼성전자','ACTOR'),('b','삼성전자 우선주','INSTRUMENT'),('c','0001A0','INSTRUMENT')])

    def tearDown(self):
        self.tmp.cleanup()

    def test_connection_expansion_includes_all_incoming_rows_and_rejects_invented_rows(self):
        fk={'table':'actor','target_table':'entity','columns':['actor_id','entity_type'],'target_columns':['entity_id','entity_type']}
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('CREATE TABLE actor(actor_id TEXT, entity_type TEXT, note TEXT)')
            c.executemany('INSERT INTO actor VALUES(?,?,?)',[('a','ACTOR',str(i)) for i in range(25)]+[('a','INSTRUMENT','wrong type')])
            c.execute('CREATE TABLE _metadata(payload TEXT)')
            c.execute('INSERT INTO _metadata VALUES(?)',(json.dumps({'foreign_keys':[fk],'tables':{'actor':{'complete':False}}}),))
        row={'entity_id':'a','display_name':'삼성전자','entity_type':'ACTOR'}
        result=row_connections(self.path,'entity',row)
        self.assertEqual(len(result['edges']),25)
        self.assertEqual(len(result['nodes']),26)
        self.assertEqual(result['partial_tables'],['actor'])
        outgoing=row_connections(self.path,'actor',{'actor_id':'a','entity_type':'ACTOR','note':'0'})
        self.assertEqual(len(outgoing['edges']),1)
        with self.assertRaises(ValueError): row_connections(self.path,'entity',{**row,'display_name':'invented'})
        with self.assertRaises(ValueError): row_connections(self.path,'entity;DROP TABLE entity',row)

    def test_search_sort_and_exact_link_do_not_merge_company_and_security(self):
        result = browse(self.path, 'entity', search='삼성', sort='entity_id', direction='desc', limit=1)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['rows'][0]['entity_id'], 'b')
        exact = browse(self.path, 'entity', field='entity_id', value='a')
        self.assertEqual([r['entity_type'] for r in exact['rows']], ['ACTOR'])

    def test_catalog_has_no_inspector_page_limit_and_preserves_type_boundary(self):
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('CREATE TABLE company_profile(actor_id TEXT)')
            c.executemany('INSERT INTO entity VALUES(?,?,?)',[(f'actor_{i}',f'company {i}','ACTOR') for i in range(2400)])
            c.executemany('INSERT INTO company_profile VALUES(?)',[(f'actor_{i}',) for i in range(2400)])
        catalog=entity_catalog(self.path,'COMPANY')
        self.assertEqual(catalog['total'],2400)
        self.assertEqual(len({r['entity_id'] for r in catalog['rows']}),2400)
        self.assertTrue(all(r['entity_type']=='ACTOR' for r in catalog['rows']))
        with self.assertRaises(ValueError): entity_catalog(self.path,'COMPANY; DROP TABLE entity')

    def test_identifiers_cannot_inject_sql(self):
        for kwargs in ({'table':'entity; DROP TABLE entity'}, {'table':'entity','sort':'not_a_column'}, {'table':'entity','field':'not_a_column'}):
            with self.assertRaises(ValueError):
                browse(self.path, **kwargs)
        self.assertEqual(browse(self.path,'entity',search="' OR 1=1 --")['total'],0)

    def test_composite_fk_does_not_link_distinct_companies_by_shared_type(self):
        fk={'columns':['actor_id','actor_type'],'target_columns':['actor_id','actor_type']}
        self.assertFalse(matches_fk({'actor_id':'a','actor_type':'COMPANY'},{'actor_id':'b','actor_type':'COMPANY'},fk))
        self.assertTrue(matches_fk({'actor_id':'a','actor_type':'COMPANY'},{'actor_id':'a','actor_type':'COMPANY'},fk))
        self.assertFalse(matches_fk({'actor_id':None,'actor_type':'COMPANY'},{'actor_id':None,'actor_type':'COMPANY'},fk))

    def test_numeric_sort_preserves_exact_source_values(self):
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('CREATE TABLE business_segment_fact(fact_id TEXT, revenue_krw TEXT)')
            c.executemany('INSERT INTO business_segment_fact VALUES(?,?)',[('a','10'),('b','2'),('c','9007199254740993'),('d','9007199254740992')])
            c.execute('CREATE TABLE _metadata(payload TEXT)')
            c.execute('INSERT INTO _metadata VALUES(?)',(json.dumps({'schema':{'business_segment_fact':[{'name':'revenue_krw','type':'numeric'}]}}),))
        rows=browse(self.path,'business_segment_fact',sort='revenue_krw')['rows']
        self.assertEqual([r['revenue_krw'] for r in rows],['2','10','9007199254740992','9007199254740993'])

    def test_review_is_bound_to_evidence_version_and_preserves_history(self):
        path = Path(self.tmp.name) / 'reviews.sqlite3'
        first = {'edge_key':'issuer:a:b','evidence_hash':fingerprint({'issuer':'a'}),'status':'confirmed','note':'공시 대조'}
        save_review(path,first)
        save_review(path,{**first,'status':'rejected'})
        result=read_reviews(path)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['status'],'rejected')
        self.assertNotEqual(first['evidence_hash'],fingerprint({'issuer':'c'}))
        with self.assertRaises(ValueError):
            save_review(path,{**first,'status':'silently_update_source'})


if __name__ == '__main__':
    unittest.main()
