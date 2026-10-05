"""A view proposal must not disguise unsupported values or deployed state."""
import copy
import json
import unittest
from pathlib import Path

from paths import APP, METADATA, EDGE_ONTOLOGY
from ontology.oms.loader import read_definitions
from backend.view_design import build_catalog


class ViewDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = read_definitions(METADATA / 'object_types', EDGE_ONTOLOGY / 'metadata')
        cls.plan = json.loads((APP / 'data/view-design.json').read_text(encoding='utf8'))

    def catalog(self):
        return build_catalog(self.docs, self.plan)

    def test_all_types_have_explicit_proposals_not_deployment_claims(self):
        result = self.catalog()
        self.assertEqual(len(result['objects']), 23)
        self.assertEqual(len(result['relations']), 37)
        self.assertEqual(result['status'], 'design_only')
        self.assertFalse(result['modelChanged'])
        names = [v['viewName'] for v in result['objects'] + result['relations']]
        self.assertEqual(len(set(names)), 60)
        self.assertTrue(all(len(n.split('.')[1].encode()) <= 63 for n in names))

    def test_unknown_cost_basis_cannot_be_exposed_as_confirmed_value(self):
        obj = next(o for o in self.catalog()['objects'] if o['id'] == 'MarketCapitalization')
        cols = {c['property']: c for c in obj['columns']}
        self.assertEqual(cols['amount']['valuePolicy'], 'typed_null_pending')
        self.assertEqual(cols['currencyCode']['valuePolicy'], 'typed_null_pending')
        self.assertIn('currencyCode', {x['property'] for x in obj['columns']})

    def test_composite_identity_keeps_versions_and_encoding_contract(self):
        obj = next(o for o in self.catalog()['objects'] if o['id'] == 'FinancialMetric')
        self.assertIn('raw_run_id', obj['identity']['columns'])
        self.assertEqual(obj['identity']['encoding'], 'jsonStringArray')
        self.assertEqual(len(obj['identity']['columns']), 7)

    def test_multiple_roles_keep_participation_identity(self):
        rel = next(r for r in self.catalog()['relations'] if r['id'] == 'Company_ParticipatesIn_SourceEvent')
        self.assertEqual(rel['sourceMapping']['identity'], ['event_argument_id'])
        self.assertTrue({'role_code', 'mentioned_name'} <= {c['column'] for c in rel['columns']})
        self.assertEqual(rel['rowPolicy'], 'preserve_source_records')

    def test_missing_design_fails_instead_of_silently_dropping_type(self):
        plan = copy.deepcopy(self.plan)
        del plan['objects']['Company']
        with self.assertRaises(ValueError):
            build_catalog(self.docs, plan)

    def test_definition_change_marks_design_stale(self):
        docs = copy.deepcopy(self.docs)
        docs[0][1]['_definitionSources']['object_types/Company.yaml'] += '\n# changed\n'
        self.assertTrue(build_catalog(docs, self.plan)['modelChanged'])

    def test_calculation_edges_are_blocked_not_empty_success(self):
        rel = next(r for r in self.catalog()['relations'] if r['id'] == 'FinancialMetric_CalculatedFrom_FinancialMetric')
        self.assertEqual(rel['readiness'], 'blocked')


if __name__ == '__main__':
    unittest.main()
