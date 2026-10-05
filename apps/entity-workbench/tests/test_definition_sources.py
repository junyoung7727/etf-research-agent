import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from ontology.oms.loader import read_definitions
from backend.definition_sources import source_state, promote_definitions


class DefinitionSourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root / 'library'
        self.drafts = self.root / 'drafts'
        for root in (self.library, self.drafts):
            (root / 'object_types').mkdir(parents=True)
            (root / 'link_types').mkdir()

    def put(self, root, name, **extra):
        path = root / 'object_types' / (name + '.yaml')
        path.write_text(yaml.safe_dump(dict(name=name, links=[], **extra)), encoding='utf8')
        return path

    def test_union_resolves_links_across_sources_without_copying(self):
        self.put(self.library, 'Company')
        self.put(self.drafts, 'Equity', linkTypes=['Equity_IssuedBy_Company'])
        link = self.library / 'link_types/Equity_IssuedBy_Company.yaml'
        link.write_text(yaml.safe_dump(dict(id=link.stem, source='Equity', definition={'target':'Company'})), encoding='utf8')
        docs = read_definitions(self.drafts / 'object_types', self.library)
        self.assertEqual([d['name'] for _, d, _ in docs], ['Company', 'Equity'])
        self.assertEqual(docs[1][1]['links'], [{'target': 'Company'}])
        self.assertFalse((self.drafts / 'object_types/Company.yaml').exists())

    def test_promote_preserves_graph_and_removes_only_promoted_drafts(self):
        self.put(self.library, 'Company')
        self.put(self.drafts, 'Equity')
        before = source_state(self.drafts, self.library)
        promote_definitions(self.drafts, self.library, before['sourceHash'])
        after = source_state(self.drafts, self.library)
        self.assertEqual(after['pending'], [])
        self.assertTrue((self.library / 'object_types/Equity.yaml').exists())
        self.assertEqual(len(read_definitions(self.drafts / 'object_types', self.library)), 2)

    def test_conflicts_and_stale_read_cannot_overwrite_library(self):
        self.put(self.library, 'Company')
        before = source_state(self.drafts, self.library)
        self.put(self.drafts, 'Equity')
        with self.assertRaises(ValueError):
            promote_definitions(self.drafts, self.library, before['sourceHash'])
        self.put(self.drafts, 'Company', description='different')
        with self.assertRaisesRegex(ValueError, 'Company'):
            read_definitions(self.drafts / 'object_types', self.library)

    def test_failed_write_keeps_drafts_and_rolls_back_library(self):
        self.put(self.drafts, 'Company')
        self.put(self.drafts, 'Equity')
        state = source_state(self.drafts, self.library)
        from backend.file_changes import replace_file
        calls = []
        def fail_once(path, content):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('simulated disk error')
            replace_file(path, content)
        with patch('backend.file_changes.replace_file', side_effect=fail_once):
            with self.assertRaises(OSError):
                promote_definitions(self.drafts, self.library, state['sourceHash'])
        self.assertEqual(len(list((self.drafts / 'object_types').glob('*.yaml'))), 2)
        self.assertEqual(list((self.library / 'object_types').glob('*.yaml')), [])
