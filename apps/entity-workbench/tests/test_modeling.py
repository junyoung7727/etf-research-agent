from contextlib import closing
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.modeling import validate_model, preview_object, save_model, read_model, Conflict


class ModelingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.snapshot=Path(self.tmp.name)/'snapshot.sqlite3'
        self.store=Path(self.tmp.name)/'model.sqlite3'
        self.meta={'schema':{'entity':[{'name':'entity_id','type':'text'},{'name':'display_name','type':'text'}],
                             'actor':[{'name':'actor_id','type':'text'},{'name':'actor_type','type':'text'}]},
                   'foreign_keys':[{'table':'actor','target_table':'entity','columns':['actor_id'],'target_columns':['entity_id']}],
                   'tables':{'entity':{'complete':True},'actor':{'complete':True}}}
        self.model={'objects':[{'id':'Company','label':'회사','table':'actor','key':'actor_id','note':'검토 중',
                 'joins':[{'id':'j1','from':'base','fk':0,'reverse':False}],
                 'properties':[{'id':'name','label':'이름','source':'j1','column':'display_name'}]}], 'relations':[]}
        with closing(sqlite3.connect(self.snapshot)) as c, c:
            c.executescript('CREATE TABLE entity(entity_id TEXT,display_name TEXT); CREATE TABLE actor(actor_id TEXT,actor_type TEXT);')
            c.executemany('INSERT INTO entity VALUES(?,?)',[('a','삼성전자'),('b','삼성전자 우선주')])
            c.execute("INSERT INTO actor VALUES('a','COMPANY')")
            c.execute('CREATE TABLE _metadata(payload TEXT)')
            c.execute('INSERT INTO _metadata VALUES(?)',(json.dumps(self.meta),))

    def tearDown(self): self.tmp.cleanup()

    def test_explicit_mapping_produces_one_company_and_preserves_source_rows(self):
        result=preview_object(self.snapshot,self.model,'Company')
        self.assertEqual(result['stats']['base_rows'],1)
        self.assertEqual(result['stats']['joined_rows'],1)
        self.assertEqual(result['rows'][0]['values']['name'],'삼성전자')
        self.assertEqual(result['rows'][0]['sources']['j1']['entity_id'],'a')
        self.assertEqual(result['stats']['duplicate_ids'],0)

    def test_fanout_and_null_identifiers_are_reported_not_silently_merged(self):
        with closing(sqlite3.connect(self.snapshot)) as c, c:
            c.execute("INSERT INTO entity VALUES('a','동일 ID 중복')")
            c.execute("INSERT INTO actor VALUES(NULL,'COMPANY')")
        result=preview_object(self.snapshot,self.model,'Company')
        self.assertEqual(result['stats']['joined_rows'],3)
        self.assertEqual(result['stats']['duplicate_ids'],1)
        self.assertEqual(result['stats']['null_ids'],1)
        self.assertEqual(len(result['rows']),3)

    def test_invalid_columns_and_unjoined_sources_are_rejected(self):
        for key,value in [('table','actor;DROP TABLE entity'),('key','missing')]:
            bad=copy.deepcopy(self.model);bad['objects'][0][key]=value
            with self.assertRaises(ValueError): validate_model(bad,self.meta)
        bad=copy.deepcopy(self.model);bad['objects'][0]['properties'][0]['source']='not_joined'
        with self.assertRaises(ValueError): validate_model(bad,self.meta)

    def test_changed_fk_and_invalid_relation_do_not_silently_change_meaning(self):
        bad=copy.deepcopy(self.model)
        bad['objects'][0]['joins'][0]['definition']={'table':'different'}
        with self.assertRaises(ValueError): validate_model(bad,self.meta)
        bad=copy.deepcopy(self.model)
        bad['relations']=[{'id':'Issues','label':'발행','source':'Company','target':'Missing',
                          'source_property':'id','target_property':'id','cardinality':'1:N'}]
        with self.assertRaises(ValueError): validate_model(bad,self.meta)

    def test_drafts_are_versioned_and_stale_editors_cannot_overwrite(self):
        first=save_model(self.store,self.model,0,self.meta)
        self.assertEqual(first['revision'],1)
        with self.assertRaises(Conflict): save_model(self.store,self.model,0,self.meta)
        second=save_model(self.store,self.model,1,self.meta)
        self.assertEqual(second['revision'],2)
        self.assertEqual(read_model(self.store)['model'],self.model)
        with closing(sqlite3.connect(self.store)) as c: self.assertEqual(c.execute('SELECT count(*) FROM model_revision').fetchone()[0],2)


if __name__=='__main__': unittest.main()
