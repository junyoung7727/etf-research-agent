import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import cq_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_trend_orders_releases_and_counts_criteria_without_turning_missing_into_failure(self):
        versions=[{'id':'v2','release':2,'label':'v2','run_count':1},
            {'id':'unversioned','release':0,'label':'unknown','run_count':9},
            {'id':'v1','release':1,'label':'v1','run_count':1},
            {'id':'v3','release':3,'label':'v3','run_count':0}]
        data={'agent_versions':versions,'runs':[]}
        def rows(data,version):
            checks=[{'id':identifier,'group':group,'status':status} for identifier,group,status in [
                ('accuracy','common','pass'),('reasoning','common','fail'),
                ('research','common','unknown'),('fulfillment','cq','pass')]]
            return [{'run_id':None if version=='v3' else 'run','checks':[] if version=='v3' else checks,
                     'contract_version':3}]
        with patch.object(cq_benchmark,'catalog',return_value=data),patch.object(cq_benchmark,'matrix_rows',side_effect=rows):
            points=cq_benchmark.trend()['points']
        self.assertEqual([p['id'] for p in points],['v1','v2','v3'])
        self.assertEqual(points[0]['common']['pass'],1)
        self.assertEqual(points[0]['common']['fail'],1)
        self.assertEqual(points[0]['common']['unknown'],1)
        self.assertEqual(points[0]['common']['total'],3)
        self.assertEqual(points[0]['cq']['pass'],1)
        self.assertEqual(points[0]['total']['pass'],2)
        self.assertEqual(points[0]['total']['total'],4)
        self.assertEqual(points[0]['total']['unknown'],1)
        self.assertEqual(points[2]['common']['not_run'],3)
        self.assertEqual(points[2]['common']['fail'],0)
        self.assertIsNone(points[2]['common']['plotted_pass'])
        self.assertIsNone(points[2]['total']['plotted_pass'])

    def test_trend_distinguishes_actual_zero_passes_from_an_unevaluated_run(self):
        data={'agent_versions':[{'id':'v1','release':1,'label':'v1','run_count':1}],'runs':[]}
        row={'run_id':'run','checks':[{'id':'accuracy','status':'fail'}],'contract_version':3}
        with patch.object(cq_benchmark,'catalog',return_value=data),patch.object(cq_benchmark,'matrix_rows',return_value=[row]):
            point=cq_benchmark.trend()['points'][0]
        self.assertEqual(point['common']['plotted_pass'],0)
        self.assertEqual(point['common']['not_evaluated'],2)
        self.assertIsNone(point['cq']['plotted_pass'])

    def test_matrix_keeps_versions_separate_and_never_hides_latest_failure(self):
        cases=[{'id':f'CQ{i:02}','title':f'Question {i}'} for i in range(1,14)]
        runs=[{'run_id':name,'case':'CQ01','status':status,'agent_version':{'id':version}} for name,status,version in [
            ('CQ01-suite-20261005T100000Z','answered','v1'),
            ('CQ01-suite-20261005T110000Z','error','v1'),
            ('CQ01-suite-20261005T120000Z','answered','v2'),
            ('CQ01-pilot-20261005T130000Z','answered','v1')]]
        catalog={'cases':cases,'runs':runs,'agent_versions':[{'id':'v1','run_count':3},{'id':'v2','run_count':1},
            {'id':'v3','run_count':0}]}
        result={'overall':'fail','review_status':'missing','agent_checks':[],
            'code_checks':[{'status':'fail'}],'contract':{'version':3}}
        with patch.object(cq_benchmark,'catalog',return_value=catalog),patch.object(cq_benchmark,'run_directory',side_effect=lambda x:x),patch.object(cq_benchmark,'evaluate',return_value=result):
            one=cq_benchmark.matrix('v1');two=cq_benchmark.matrix('v2');empty=cq_benchmark.matrix('v3')
            self.assertEqual(len(one['rows']),13)
            self.assertEqual(one['rows'][0]['run_id'],'CQ01-suite-20261005T110000Z')
            self.assertEqual(one['rows'][0]['execution_status'],'error')
            self.assertEqual(one['rows'][1]['overall'],'not_run')
            self.assertEqual(two['rows'][0]['run_id'],'CQ01-suite-20261005T120000Z')
            self.assertTrue(all(r['overall']=='not_run' for r in empty['rows']))
            with self.assertRaises(ValueError):cq_benchmark.matrix('unknown-version')

    def test_old_runs_are_not_assigned_to_the_current_release(self):
        with patch.object(cq_benchmark,'release',return_value={'version':1,'source_digest':'new','summary':'Initial'}):
            versions=cq_benchmark.version_index([{'code_commit':'old','case':'CQ01'}])
        self.assertEqual(cq_benchmark.version_id({'code_commit':'old'}),'unversioned')
        self.assertEqual({v['id'] for v in versions},{'unversioned','release-1-unrun'})

    def test_final_output_requires_actual_claims_with_successful_evidence_for_each(self):
        from integration.run_cq_agent import valid_citations,OUTPUT
        from jsonschema import Draft202012Validator
        calls=[{'error':None,'response':{'tool_run_id':'good'}},{'error':'Unavailable','response':{'tool_run_id':'bad'}}]
        response={'answer':'placeholder','claims':[],'limitations':[]}
        self.assertFalse(valid_citations(response,calls))
        self.assertFalse(Draft202012Validator(OUTPUT).is_valid(response))
        response['claims']=[{'claim':'Observed fact','tool_run_ids':['good'],'purpose':'Answer requested scope','evidence_role':'support'}]
        self.assertTrue(valid_citations(response,calls))
        response['claims'].append({'claim':'Unsupported extra','tool_run_ids':[],'purpose':'Extra'})
        self.assertFalse(valid_citations(response,calls))
        response['claims'][-1]['tool_run_ids']=['bad']
        self.assertFalse(valid_citations(response,calls))
        response['claims'][-1].update(claim='The comparison was rejected',evidence_role='limitation')
        self.assertTrue(valid_citations(response,calls))
        response['claims'][-1]['tool_run_ids']=['not_saved']
        self.assertFalse(valid_citations(response,calls))

    def test_new_failed_run_replaces_old_pass_without_counting_pilots_or_efficiency(self):
        runs=[{'run_id':name,'status':'answered','semantic_grade':grade} for name,grade in [
            ('CQ09-suite-20261005T160000Z','passed'),('CQ09-cloud-20261005T170000Z','failed'),
            ('CQ09-pilot-20261005T180000Z','passed'),('EFF30-20261005T190000Z','passed'),
            ('CQ11-suite-20261005T160000Z','passed')]]
        latest=cq_benchmark.latest_cases(runs)
        self.assertEqual([(r['case'],r['semantic_grade']) for r in latest],[('CQ09','failed'),('CQ11','passed')])

    def test_model_request_count_includes_schema_rejections_but_not_output_format_tool(self):
        from integration.run_cq_agent import model_call_count
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model';path.mkdir()
            events=[{'message':{'content':[{'name':name,'input':{},'id':str(i)}]}}
                for i,name in enumerate(['mcp__analysis__get_objects','mcp__analysis__get_objects','StructuredOutput'])]
            (path/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf8')
            self.assertEqual(model_call_count(Path(tmp)),2)

    def test_answered_does_not_become_passed_or_eighty_percent_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'CQ07-example';folder.mkdir()
            (folder/'benchmark.json').write_text(json.dumps({'status':'answered','semantic_grade':'not_reviewed'}),encoding='utf8')
            with patch.object(cq_benchmark,'RUNS',Path(tmp)):
                data=cq_benchmark.catalog()
                self.assertEqual(data['coverage']['status'],'not_measured')
                self.assertEqual(data['runs'][0]['semantic_grade'],'not_reviewed')
                self.assertEqual(data['implementation_status'],'in_progress')

    def test_evidence_path_cannot_escape_run_directory(self):
        for run,tool in [('../secrets','cq_'+'a'*32),('CQ07','../../secret'),('CQ07','cq_'+'a'*32+'/other')]:
            with self.assertRaises(ValueError):cq_benchmark.evidence(run,tool)
