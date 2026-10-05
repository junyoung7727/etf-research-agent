import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import cq_benchmark


class BenchmarkTests(unittest.TestCase):
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
