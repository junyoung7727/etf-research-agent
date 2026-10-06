import copy
import asyncio
from dataclasses import dataclass
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from backend import cq_benchmark
from backend import cq_evaluation as evaluation


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'CQ05-suite-20261005T170000Z';self.run.mkdir()
        self.id='cq_'+'a'*32
        self.report={'case':'CQ05-suite','status':'answered','semantic_grade':'passed',
            'question':'한 달 전망','cutoff':'2026-10-05T00:00:00+00:00','elapsed_ms':1000,
            'response':{'answer':'우선협상 선정이다.','limitations':[],
                'claims':[{'claim':'우선협상 선정이다.','purpose':'사업 단계 확인','evidence_role':'support','tool_run_ids':[self.id]}]}}
        self.call={'tool':'search_events','arguments':{},'cutoff':self.report['cutoff'],
            'error':None,'elapsed_ms':10,'queries':[],'finished_at':'2026-10-05T01:00:00+00:00',
            'response':{'tool_run_id':self.id,'result':{'items':[{'stage':'preferred_bidder'}]}}}
        (self.run/'tools').mkdir();self.save()

    def save(self):
        (self.run/'benchmark.json').write_text(json.dumps(self.report),encoding='utf8')
        (self.run/'tools'/(self.id+'.json')).write_text(json.dumps(self.call),encoding='utf8')

    def result(self):return evaluation.evaluate(self.run)

    def review(self):
        result=self.result()
        return {'checks':[{'id':r['id'],'status':'pass','reason':'저장된 답변과 자료에서 확인',
            'answer_span':'우선협상 선정이다.','evidence_ids':[self.id]} for r in result['agent_checks']],
            'unnecessary_calls':[]}

    def test_legacy_pass_cannot_pass_new_contract_and_reproduction_is_excluded(self):
        result=self.result()
        self.assertEqual(result['overall'],'not_evaluated')
        self.assertTrue(all(r['status']=='pass' for r in result['code_checks']))
        self.assertNotIn('reproduction',json.dumps(result['code_checks']))
        self.assertEqual(result['efficiency']['reference_calls'],None)
        self.assertEqual(result['efficiency']['actual_calls'],1)

    def test_failed_tool_may_support_limitation_but_not_fact(self):
        self.call['error']='missing';self.save()
        self.assertEqual(self.result()['overall'],'fail')
        self.report['response']['claims'][0]['evidence_role']='limitation';self.save()
        self.assertEqual(self.result()['overall'],'not_evaluated')

    def test_empty_answer_or_missing_reference_is_a_code_failure(self):
        self.report['response']['answer']='';self.save()
        self.assertEqual(self.result()['overall'],'fail')
        self.report['response']['answer']='답변';self.report['response']['claims'][0]['tool_run_ids']=['missing'];self.save()
        self.assertEqual(self.result()['overall'],'fail')

    def test_malformed_output_is_a_failed_check_not_a_dashboard_crash(self):
        self.report['response']=['invalid'];self.save()
        self.assertEqual(self.result()['overall'],'fail')

    def test_cutoff_mismatch_is_rejected_but_finished_at_after_cutoff_is_normal(self):
        self.assertEqual(self.result()['code_checks'][-1]['status'],'pass')
        self.call['cutoff']='2026-10-06T00:00:00+00:00';self.save()
        self.assertEqual(self.result()['code_checks'][-1]['status'],'fail')

    def test_complete_review_passes_but_single_semantic_failure_cannot_be_averaged(self):
        review=self.review();evaluation.save_review(self.run,review,reviewer={'model':'test','method':'fixture'})
        self.assertEqual(self.result()['overall'],'pass')
        review['checks'][0]['status']='fail'
        evaluation.save_review(self.run,review,reviewer={'model':'test','method':'fixture'})
        self.assertEqual(self.result()['overall'],'fail')

    def test_unknown_judgment_does_not_pass(self):
        review=self.review();review['checks'][0]['status']='unknown'
        evaluation.save_review(self.run,review,reviewer={'model':'test','method':'fixture'})
        self.assertEqual(self.result()['overall'],'review_needed')

    def test_uncalibrated_agent_pass_is_a_proposal_not_a_verified_pass(self):
        evaluation.save_review(self.run,self.review(),reviewer={'model':'test','calibration':'not_calibrated'})
        self.assertEqual(self.result()['overall'],'review_needed')
        self.assertEqual(self.result()['agent_proposal'],'pass')

    def test_review_must_cover_every_criterion_once_with_real_quotes_and_evidence(self):
        valid=self.review()
        for mutate in [lambda r:r['checks'].pop(),
                       lambda r:r['checks'].append(copy.deepcopy(r['checks'][0])),
                       lambda r:r['checks'][0].update(answer_span='꾸며낸 문장'),
                       lambda r:r['checks'][0].update(evidence_ids=['not_saved']),
                       lambda r:r['checks'][0].update(reason='')]:
            value=copy.deepcopy(valid);mutate(value)
            with self.assertRaises(ValueError):evaluation.save_review(self.run,value,reviewer={})

    def test_modified_evidence_invalidates_old_review(self):
        evaluation.save_review(self.run,self.review(),reviewer={'model':'test'})
        self.call['response']['result']['items'][0]['stage']='signed';self.save()
        result=self.result()
        self.assertEqual(result['overall'],'not_evaluated')
        self.assertEqual(result['review_status'],'stale')

    def test_frozen_run_contract_survives_later_contract_changes(self):
        evaluation.freeze_contract(self.run,self.report['case'])
        evaluation.save_review(self.run,self.review(),reviewer={'model':'test'})
        with patch.object(evaluation,'contract_for',side_effect=AssertionError('Must use the run contract')):
            self.assertEqual(self.result()['overall'],'pass')
        with self.assertRaises(FileExistsError):evaluation.freeze_contract(self.run,self.report['case'])

    def test_unnecessary_call_requires_reason_and_distinct_real_id(self):
        review=self.review();review['unnecessary_calls']=[{'tool_run_id':self.id,'reason':'같은 범위의 목적 없는 반복'}]
        evaluation.save_review(self.run,review,reviewer={'model':'test'})
        self.assertEqual(self.result()['efficiency']['unnecessary_calls'],1)
        review['unnecessary_calls'].append(review['unnecessary_calls'][0])
        with self.assertRaises(ValueError):evaluation.save_review(self.run,review,reviewer={})

    def test_same_run_links_and_paginated_trace_survive_refresh(self):
        model=self.run/'model';model.mkdir()
        events=[{'message_type':'AssistantMessage','message':{'content':[{'type':'text','text':str(i)}]}} for i in range(3)]
        (model/'events.jsonl').write_text('\n'.join(map(json.dumps,events)),encoding='utf8')
        with patch.object(cq_benchmark,'RUNS',self.root):
            detail=cq_benchmark.detail(self.run.name)
            self.assertIn(self.run.name,detail['analysis_url'])
            self.assertIn(self.run.name,detail['benchmark_url'])
            trace=cq_benchmark.trace(self.run.name,offset='1',limit='1')
            self.assertEqual(trace['events'][0]['message']['content'][0]['text'],'1')
            self.assertEqual(trace['next_offset'],2)
            with self.assertRaises(ValueError):cq_benchmark.detail('../escape')
            with self.assertRaises(ValueError):cq_benchmark.trace(self.run.name,offset='-1')

    def test_contracts_cover_thirteen_cqs_without_invented_reference_counts(self):
        for i in range(1,14):
            contract=evaluation.contract_for(f'CQ{i:02}')
            self.assertGreaterEqual(len(contract['required_findings']),3)
            self.assertIsNone(contract['reference_execution'])
            self.assertTrue(contract['reference_path'])

    def test_one_review_has_four_quality_verdicts_and_separate_code_checks(self):
        for i in range(1,14):
            self.report['case']=f'CQ{i:02}-suite';self.save()
            result=self.result()
            self.assertEqual([r['id'] for r in result['agent_checks']],['accuracy','reasoning','research','fulfillment'])
            self.assertEqual([r['group'] for r in result['agent_checks']],['common','common','common','cq'])
            self.assertEqual(len(result['code_checks']),3)
            self.assertEqual(result['contract']['version'],3)

    def test_old_contract_review_remains_on_disk_but_cannot_pass_four_criteria(self):
        with patch.object(evaluation,'contract_for',return_value={'id':'CQ05','version':2,'common':[],
                'required_findings':[],'critical_errors':[],'completion_conditions':'old contract'}):
            evaluation.save_review(self.run,self.review(),reviewer={'model':'test'})
        previous=(self.run/'evaluation.json').read_bytes()
        result=self.result()
        self.assertEqual(result['review_status'],'stale')
        self.assertEqual(result['overall'],'not_evaluated')
        self.assertEqual((self.run/'evaluation.json').read_bytes(),previous)
        self.assertTrue(all(r['status']=='not_evaluated' for r in result['agent_checks']))

    def test_judge_packet_hides_old_grade_and_schema_accepts_complete_review(self):
        from integration.judge_cq import packet,output_schema
        from jsonschema import Draft202012Validator
        result,initial,values=packet(self.run)
        self.assertNotIn('semantic_grade',initial)
        self.assertNotIn('model',initial)
        self.assertIn(self.id,values)
        self.assertEqual(len(initial['checks']),4)
        schema=output_schema([r['id'] for r in result['agent_checks']])
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.review())

    def test_one_evaluator_session_returns_all_four_verdicts_and_reads_saved_records(self):
        from integration.judge_cq import judge
        model=self.run/'model';model.mkdir()
        (model/'events.jsonl').write_text('{"message_type":"ResultMessage","message":{}}\n',encoding='utf8')
        submitted=[];clients=[];readers={};review=self.review();evidence_id=self.id

        @dataclass
        class ResultMessage:
            structured_output:dict
            subtype:str='success'
            is_error:bool=False

        def tool(name,*args):
            def register(fn):readers[name]=fn;return fn
            return register

        class Client:
            def __init__(self,**kwargs):clients.append(kwargs)
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def query(self,value):
                submitted.append(json.loads(value))
                await readers['read_record']({'id':evidence_id})
                await readers['read_record']({'id':'trace'})
            async def receive_response(self):yield ResultMessage(review)

        sdk=SimpleNamespace(ClaudeAgentOptions=lambda **kwargs:kwargs,ClaudeSDKClient=Client,
            create_sdk_mcp_server=lambda **kwargs:kwargs,tool=tool)
        with patch.dict(sys.modules,{'claude_agent_sdk':sdk}),patch('integration.judge_cq.check',return_value={'version':1,'source_digest':'fixture'}):
            result=asyncio.run(judge(self.run,model='fixture',key='test-key'))
        self.assertEqual(len(clients),1)
        self.assertEqual(len(submitted),1)
        self.assertEqual([c['id'] for c in submitted[0]['checks']],['accuracy','reasoning','research','fulfillment'])
        self.assertNotIn('code_checks',submitted[0])
        self.assertIn('trace',submitted[0]['available_records'])
        self.assertEqual(result['review_status'],'current')
        self.assertEqual(result['overall'],'review_needed')
        self.assertEqual(len(list((self.run/'evaluations').iterdir())),1)


if __name__=='__main__':unittest.main()
