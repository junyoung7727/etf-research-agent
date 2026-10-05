import copy
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from paths import EDGE_ONTOLOGY
from backend.interface_types import read_catalog, save_catalog, promote_catalog
from backend.value_types import RevisionConflict, SourceConflict
from ontology.oms.loader import read_definitions

from ontology.oms.interfaces import validate_interfaces


class InterfaceContractTest(unittest.TestCase):
    def setUp(self):
        self.objects = {
            'Company': {'name': 'Company', 'primaryKey': 'id', 'properties': {
                'id': {'dataType': 'String', 'nullable': False},
                'name': {'dataType': 'String', 'nullable': True}}},
            'Event': {'name': 'Event', 'primaryKey': 'id', 'properties': {}}}
        self.links = {'participation': {'source': 'Company', 'definition': {
            'target': 'Event', 'cardinality': 'N:N'}}}
        self.contract = {'formatVersion': 1, 'name': 'Actor', 'displayName': 'Actor',
            'description': 'A participant in an event.',
            'properties': {'id': {'dataType': 'String', 'nullable': False, 'description': 'Original object ID.'},
                           'name': {'dataType': 'String', 'nullable': True, 'description': 'Name of the actor.'}},
            'links': {'participatesIn': {'target': {'kind': 'object', 'name': 'Event'},
                'cardinality': 'MANY', 'required': True, 'description': 'Events involving this actor.'}},
            'implementations': {'Company': {'properties': {'id': 'id', 'name': 'name'},
                'links': {'participatesIn': {'linkType': 'participation', 'direction': 'forward'}}}}}

    def check(self):
        return validate_interfaces([self.contract], self.objects, self.links)

    def test_valid_contract_preserves_concrete_identity(self):
        self.check()

    def test_missing_property_and_incompatible_type_rejected(self):
        del self.contract['implementations']['Company']['properties']['name']
        with self.assertRaisesRegex(ValueError, 'name'): self.check()
        self.contract['implementations']['Company']['properties']['name'] = 'name'
        self.contract['properties']['name']['dataType'] = 'Long'
        with self.assertRaisesRegex(ValueError, '타입'): self.check()

    def test_nullable_source_cannot_promise_non_null(self):
        self.contract['properties']['name']['nullable'] = False
        with self.assertRaisesRegex(ValueError, 'NULL'): self.check()

    def test_id_cannot_map_to_display_name(self):
        self.contract['implementations']['Company']['properties']['id'] = 'name'
        with self.assertRaises(ValueError): self.check()

    def test_direction_target_and_cardinality_are_enforced(self):
        impl = self.contract['implementations']['Company']['links']['participatesIn']
        impl['direction'] = 'reverse'
        with self.assertRaisesRegex(ValueError, '방향'): self.check()
        impl['direction'] = 'forward'
        self.contract['links']['participatesIn']['target']['name'] = 'Company'
        with self.assertRaisesRegex(ValueError, '대상'): self.check()
        self.contract['links']['participatesIn']['target']['name'] = 'Event'
        self.contract['links']['participatesIn']['cardinality'] = 'ONE'
        with self.assertRaisesRegex(ValueError, '개수'): self.check()

    def test_optional_link_may_be_absent_but_required_link_must_exist(self):
        self.contract['implementations']['Company']['links'] = {}
        with self.assertRaisesRegex(ValueError, '필수'): self.check()
        self.contract['links']['participatesIn']['required'] = False
        self.check()

    def test_reverse_relationship_can_supply_common_navigation(self):
        self.links['participation'] = {'source': 'Event', 'definition': {'target': 'Company', 'cardinality': 'N:1'}}
        self.contract['implementations']['Company']['links']['participatesIn']['direction'] = 'reverse'
        self.check()

    def test_interface_target_requires_actual_implementation(self):
        other = copy.deepcopy(self.contract)
        other.update(name='Participant', links={})
        other['implementations']['Company']['links'] = {}
        self.contract['links']['participatesIn']['target'] = {'kind': 'interface', 'name': 'Participant'}
        with self.assertRaisesRegex(ValueError, '대상'):
            validate_interfaces([self.contract, other], self.objects, self.links)


class InterfacePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.library, self.drafts, self.db = root / 'library', root / 'drafts', root / 'interfaces.db'
        for kind in ('object_types', 'link_types', 'interface_types'):
            shutil.copytree(EDGE_ONTOLOGY / 'metadata' / kind, self.library / kind)
        self.drafts.mkdir()

    def read(self):
        return read_catalog(self.db, self.library, self.drafts)

    def save(self, state):
        return save_catalog(self.db, state['catalog'], state['revision'], state['sourceHash'], self.library, self.drafts)

    def apply(self, state):
        return promote_catalog(self.db, state['revision'], state['sourceHash'], self.library, self.drafts)

    def test_seed_contracts_load_and_annotate_all_six_objects(self):
        state = self.read()
        self.assertTrue(state['validation']['valid'])
        self.assertEqual({i['name'] for i in state['catalog']['interfaces']}, {'Actor', 'Security', 'SourceDocument'})
        docs = {d['name']: d for _, d, _ in read_definitions(self.drafts / 'object_types', self.library)}
        self.assertEqual(docs['Company']['implementedInterfaces'], ['Actor'])
        self.assertEqual(docs['ETF']['implementedInterfaces'], ['Security'])
        self.assertEqual(docs['FinancialReportSnapshot']['implementedInterfaces'], [])

    def test_save_is_durable_and_promotion_changes_only_interface_file(self):
        before = {p: p.read_bytes() for p in self.library.rglob('*.yaml')}
        state = self.read()
        state['catalog']['interfaces'][0]['description'] = 'Actors participating in reported events.'
        saved = self.save(state)
        self.assertEqual(saved['pendingCount'], 1)
        self.assertEqual(self.read()['catalog'], saved['catalog'])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        done = self.apply(saved)
        self.assertEqual(done['pendingCount'], 0)
        self.assertEqual(done['catalog'], saved['catalog'])
        self.assertEqual([p.name for p in before if before[p] != p.read_bytes()], ['Actor.yaml'])

    def test_stale_tabs_and_changed_object_contract_cannot_overwrite(self):
        state = self.read()
        state['catalog']['interfaces'][0]['description'] = 'Edited actor contract.'
        saved = self.save(state)
        with self.assertRaises(RevisionConflict): self.save(state)
        obj = self.library / 'object_types/Company.yaml'
        obj.write_text(obj.read_text(encoding='utf8') + '\n# external change\n', encoding='utf8')
        self.assertTrue(self.read()['sourceChanged'])
        with self.assertRaises(SourceConflict): self.apply(saved)
        self.assertEqual(self.read()['catalog'], saved['catalog'])

    def test_invalid_mapping_never_persists(self):
        state = self.read()
        state['catalog']['interfaces'][0]['implementations']['Company']['properties']['id'] = 'name'
        with self.assertRaises(ValueError): self.save(state)
        self.assertEqual(self.read()['revision'], 0)

    def test_partial_file_failure_rolls_back_and_preserves_draft(self):
        from backend.file_changes import replace_file
        before = {p: p.read_bytes() for p in (self.library / 'interface_types').glob('*.yaml')}
        state = self.read()
        for i in state['catalog']['interfaces']: i['description'] += ' Reviewed.'
        saved = self.save(state)
        calls = []
        def failing(path, content):
            calls.append(path)
            if len(calls) == 2: raise OSError('disk failure')
            replace_file(path, content)
        with patch('backend.file_changes.replace_file', side_effect=failing):
            with self.assertRaises(OSError): self.apply(saved)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(self.read()['catalog'], saved['catalog'])
