import copy
import shutil
import tempfile
import unittest
import json
import sqlite3
from contextlib import closing
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import yaml

from backend.value_types import SourceConflict, RevisionConflict, read_catalog, save_catalog, promote_catalog


class ValueTypesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.resources = self.root / 'resources'
        (self.resources / 'process/types').mkdir(parents=True)
        self.types_file = self.resources / 'process/types/deal.yaml'
        self.write(self.types_file, {'types': {'COMPANY.CONTRACT.SIGNING': {
            'family': 'COMPANY', 'note': 'A supply contract event.',
            'roles': {'required': ['SUPPLIER'], 'optional': ['CUSTOMER'],
                      'identity': ['SUPPLIER', 'CUSTOMER']},
            'predicates': ['SIGN'], 'lifecycle_model': 'DEAL'}}})
        self.write(self.resources / 'process/news_thread_contract_v0_1.yaml', {
            'types': {'COMPANY.CONTRACT.SIGNING': {'identity': {
                'required': ['SUPPLIER'], 'optional_discriminators': ['EFFECTIVE_DATE']},
                'missing_identity_policy': 'EMIT_UNKNOWN_LINK_ONLY'}},
            'tables': {'event_thread_link': {'fields': {'novelty_status': ['UNKNOWN']}}}})
        self.write(self.resources / 'process/lifecycle_models_v0_1.yaml', {
            'models': {'DEAL': {'stages': ['SIGNED'], 'terminal': ['CANCELLED']}}})
        self.db = self.root / 'drafts.sqlite3'

    def write(self, path, value):
        path.write_text(yaml.safe_dump(value), encoding='utf8')

    def read(self):
        return read_catalog(self.db, self.resources)

    def save(self, state):
        return save_catalog(self.db, state['catalog'], state['revision'],
                            state['sourceHash'], self.resources)

    def test_import_keeps_contract_disagreement_visible(self):
        state = self.read()
        event = state['catalog']['valueTypes'][0]['values'][0]
        self.assertEqual(event['rule']['required'], ['SUPPLIER', 'CUSTOMER'])
        self.assertEqual(event['origin']['contractRequired'], ['SUPPLIER'])
        self.assertTrue(event['origin']['identityConflict'])
        self.assertEqual(event['rule']['optional'], ['EFFECTIVE_DATE'])
        self.assertEqual(state['revision'], 0)
        self.assertFalse(self.db.exists(), 'Reading must not create or publish edits')

    def test_saved_draft_survives_reload_without_touching_source(self):
        original = self.types_file.read_bytes()
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Reviewed contract definition.'
        self.save(state)
        reread = self.read()
        self.assertEqual(reread['revision'], 1)
        self.assertEqual(reread['catalog']['valueTypes'][0]['values'][0]['description'],
                         'Reviewed contract definition.')
        self.assertEqual(self.types_file.read_bytes(), original)

    def test_stale_editor_cannot_overwrite_other_edit(self):
        state = self.read()
        self.save(state)
        with self.assertRaises(RevisionConflict):
            self.save(state)
        self.assertEqual(self.read()['revision'], 1)

    def test_source_change_blocks_publish(self):
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Pending edit.'
        self.save(state)
        self.types_file.write_text(self.types_file.read_text() + '\n# changed\n')
        self.assertTrue(self.read()['sourceChanged'])
        with self.assertRaises(SourceConflict):
            self.save(state)

    def test_unknown_condition_and_duplicate_code_are_rejected(self):
        state = self.read()
        event = state['catalog']['valueTypes'][0]['values'][0]
        event['rule']['required'].append('MADE_UP_ROLE')
        with self.assertRaises(ValueError):
            self.save(state)
        state = self.read()
        vt = state['catalog']['valueTypes'][0]
        vt['values'].append(copy.deepcopy(vt['values'][0]))
        with self.assertRaises(ValueError):
            self.save(state)
        self.assertFalse(self.db.exists())

    def test_empty_identity_does_not_silently_group_all_events(self):
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['rule']['required'] = []
        with self.assertRaises(ValueError):
            self.save(state)

    def test_new_string_enum_is_persisted(self):
        state = self.read()
        state['catalog']['valueTypes'].append({'id': 'ReviewState',
            'description': 'Review disposition.', 'baseType': 'String', 'usedBy': [],
            'values': [{'code': 'PENDING', 'description': 'Awaiting review.', 'group': ''}]})
        self.save(state)
        self.assertEqual(self.read()['catalog']['valueTypes'][-1]['id'], 'ReviewState')

    def test_pending_storage_contains_only_changed_fields(self):
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Reviewed.'
        self.save(state)
        with closing(sqlite3.connect(self.db)) as db:
            payload = json.loads(db.execute('SELECT payload FROM value_type_revision').fetchone()[0])
        self.assertEqual(payload, {'formatVersion': 2, 'valueTypes': [{'id': 'EventTypeCode',
            'values': [{'code': 'COMPANY.CONTRACT.SIGNING', 'description': 'Reviewed.'}]}]})

    def test_apply_updates_native_definition_and_clears_pending(self):
        doc = yaml.safe_load(self.types_file.read_text())
        doc['types']['COMPANY.CONTRACT.SIGNING']['quantities'] = {'AMOUNT': {'dtype': 'float'}}
        self.write(self.types_file, doc)
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Reviewed.'
        saved = self.save(state)
        applied = promote_catalog(self.db, saved['revision'], saved['sourceHash'], self.resources)
        self.assertEqual(applied['pendingCount'], 0)
        self.assertEqual(applied['catalog']['valueTypes'][0]['values'][0]['description'], 'Reviewed.')
        native = yaml.safe_load(self.types_file.read_text())['types']['COMPANY.CONTRACT.SIGNING']
        self.assertEqual(native['note'], 'Reviewed.')
        self.assertEqual(native['quantities'], {'AMOUNT': {'dtype': 'float'}})
        self.assertTrue(applied['catalog']['valueTypes'][0]['values'][0]['origin']['identityConflict'],
                        'A description edit must not silently reconcile conflicting rules')
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(json.loads(db.execute('SELECT payload FROM value_type_revision').fetchone()[0])['valueTypes'], [])

    def test_new_enum_moves_to_library_and_reads_without_draft_db(self):
        state = self.read()
        state['catalog']['valueTypes'].append(dict(id='ReviewState', description='Review.',
            baseType='String', usedBy=[], values=[dict(code='PENDING', description='Pending.', group='')]))
        saved = self.save(state)
        promote_catalog(self.db, saved['revision'], saved['sourceHash'], self.resources)
        independent = read_catalog(self.root / 'other.sqlite3', self.resources)
        self.assertEqual(independent['catalog']['valueTypes'][-1]['id'], 'ReviewState')
        self.assertEqual(independent['pendingCount'], 0)

    def test_apply_rejects_stale_source_and_preserves_draft(self):
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Reviewed.'
        saved = self.save(state)
        self.types_file.write_text(self.types_file.read_text() + '\n# another editor\n')
        with self.assertRaises(SourceConflict):
            promote_catalog(self.db, saved['revision'], saved['sourceHash'], self.resources)
        self.assertEqual(self.read()['pendingCount'], 1)

    def test_failed_apply_restores_native_file_and_keeps_pending_edit(self):
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Reviewed.'
        saved = self.save(state)
        original = self.types_file.read_bytes()
        from backend.file_changes import replace_file
        def fail_annotations(path, content):
            if path.name == 'enum_annotations.yaml':
                raise OSError('simulated permission failure')
            replace_file(path, content)
        with patch('backend.file_changes.replace_file', side_effect=fail_annotations):
            with self.assertRaises(OSError):
                promote_catalog(self.db, saved['revision'], saved['sourceHash'], self.resources)
        self.assertEqual(self.types_file.read_bytes(), original)
        self.assertEqual(self.read()['pendingCount'], 1)

    def test_applied_empty_delta_does_not_hide_later_library_changes(self):
        state = self.read()
        state['catalog']['valueTypes'][0]['values'][0]['description'] = 'Reviewed.'
        saved = self.save(state)
        promote_catalog(self.db, saved['revision'], saved['sourceHash'], self.resources)
        doc = yaml.safe_load(self.types_file.read_text())
        doc['types']['COMPANY.CONTRACT.SIGNING']['note'] = 'Changed in library.'
        self.write(self.types_file, doc)
        current = self.read()
        self.assertFalse(current['sourceChanged'])
        self.assertEqual(current['catalog']['valueTypes'][0]['values'][0]['description'], 'Changed in library.')

    def test_library_layout_change_preserves_source_identity_and_saved_drafts(self):
        state = self.read()
        self.save(state)
        self.assertEqual(read_catalog(self.db, self.root)['sourceHash'], state['sourceHash'])
        modern = self.root / 'modern'
        values = modern / 'metadata/value_types'
        shutil.copytree(self.resources / 'process/types', values / 'event_types')
        shutil.copy2(self.resources / 'process/lifecycle_models_v0_1.yaml', values)
        (modern / 'rules/threading').mkdir(parents=True)
        (modern / 'resources/process').mkdir(parents=True)
        shutil.copy2(self.resources / 'process/news_thread_contract_v0_1.yaml', modern / 'rules/threading')
        migrated = read_catalog(self.db, modern)
        self.assertFalse(migrated['sourceChanged'], 'Moving unchanged definitions must not invalidate a draft')
        self.assertEqual(state['sourceHash'], migrated['sourceHash'])
        self.assertEqual(migrated['revision'], 1)

    def test_api_preserves_local_write_boundary_and_reports_conflicts(self):
        from backend import server as workbench
        with patch.object(workbench, 'DATA', self.root), patch('backend.value_types.RESOURCES', self.resources):
            # Explicit injected resources avoid any dependency on the operator's EDGE checkout.
            with patch.object(workbench, 'read_value_catalog', lambda p: read_catalog(p, self.resources)), \
                 patch.object(workbench, 'save_value_catalog', lambda p, c, r, h: save_catalog(p, c, r, h, self.resources)):
                server = ThreadingHTTPServer(('127.0.0.1', 0), workbench.Handler)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                conn = HTTPConnection('127.0.0.1', server.server_port)
                try:
                    conn.request('GET', '/api/value-types')
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    state = json.loads(response.read())
                    body = json.dumps({k: state[k] for k in ('catalog', 'revision', 'sourceHash')})
                    conn.request('POST', '/api/value-types', body, {'Content-Type': 'application/json'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 403)
                    response.read()
                    headers = {'Content-Type': 'application/json', 'X-Workbench-Token': workbench.Handler.token}
                    for expected in (200, 409):
                        conn.request('POST', '/api/value-types', body, headers)
                        response = conn.getresponse()
                        self.assertEqual(response.status, expected)
                        response.read()
                finally:
                    conn.close()
                    server.shutdown()
                    server.server_close()
                    worker.join()


if __name__ == '__main__':
    unittest.main()
