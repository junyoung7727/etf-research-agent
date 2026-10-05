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
        names = [v['viewName'] for v in result['physicalTables']]
        self.assertEqual(len(set(names)), 27)  # 23 object views, 3 connection views, 1 existing table.
        self.assertTrue(all(len(n.split('.')[1].encode()) <= 63 for n in names))

    def test_unknown_cost_basis_cannot_be_exposed_as_confirmed_value(self):
        obj = next(o for o in self.catalog()['objects'] if o['id'] == 'MarketCapitalization')
        cols = {c['property']: c for c in obj['columns'] if c.get('property')}
        self.assertEqual(cols['amount']['valuePolicy'], 'typed_null_pending')
        self.assertEqual(cols['currencyCode']['valuePolicy'], 'typed_null_pending')
        self.assertIn('currencyCode', {x.get('property') for x in obj['columns']})

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
        self.assertIsNone(rel['viewName'])
        self.assertEqual(rel['physicalMapping']['kind'], 'blocked')

    def test_issuer_link_reuses_equity_fk_without_a_relation_table(self):
        result = self.catalog()
        rel = next(r for r in result['relations'] if r['id'] == 'Company_Issues_Equity')
        self.assertEqual(rel['viewName'], 'ontology_view.equity')
        self.assertEqual(rel['physicalMapping']['fromColumn'], 'issuer_id')
        self.assertEqual(rel['physicalMapping']['toColumn'], 'id')
        refs = [r for r in result['references'] if r['table'] == 'Equity']
        self.assertEqual([(r['column'], r['target']) for r in refs], [('issuer_id', 'Company')])

    def test_actor_links_share_source_preserve_role_and_choose_typed_endpoint(self):
        rels = [r for r in self.catalog()['relations'] if '_ParticipatesIn_' in r['id']]
        self.assertEqual({r['viewName'] for r in rels}, {'ontology_view.actor_participation'})
        for r in rels:
            m = r['physicalMapping']
            self.assertEqual(m['edgeIdColumns'], ['participation_id'])
            self.assertEqual(m['properties']['roleCode'], 'role_code')
        self.assertNotEqual(rels[0]['physicalMapping']['filters'], rels[1]['physicalMapping']['filters'])

    def test_company_code_is_resolved_to_id_not_labeled_as_primary_key(self):
        rel = next(r for r in self.catalog()['relations'] if r['id'] == 'FinancialMetric_ForCompany_Company')
        self.assertEqual(rel['physicalMapping']['kind'], 'resolved_fk')
        self.assertEqual(rel['physicalMapping']['toColumn'], 'company_id')
        self.assertNotEqual(rel['physicalMapping']['toColumn'], 'corp_code')

    def test_invalid_physical_column_fails_instead_of_drawing_a_false_connection(self):
        plan = copy.deepcopy(self.plan)
        plan['relations']['Company_Issues_Equity']['physicalMapping']['fromColumn'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Company_Issues_Equity'):
            build_catalog(self.docs, plan)

    def test_polymorphic_security_links_require_explicit_profile_filter(self):
        rels = [r for r in self.catalog()['relations'] if r['id'].startswith('ETFHolding_HoldsSecurity_')]
        self.assertEqual(len(rels), 2)
        self.assertEqual({r['physicalMapping']['filters']['security_type'][0] for r in rels}, {'EQUITY','ETF'})
        source = next(t for t in self.catalog()['physicalTables'] if t['id']=='ETFHolding')
        self.assertIn('security_type', {c['column'] for c in source['columns']})


if __name__ == '__main__':
    unittest.main()
