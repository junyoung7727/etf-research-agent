import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import cq_benchmark


class BenchmarkTests(unittest.TestCase):
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
