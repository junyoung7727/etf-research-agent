import copy
import unittest
from backend.view_design import read_catalog
from backend.puppygraph_schema import build_schema


class PuppyGraphSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = read_catalog()

    def test_issuer_uses_same_equity_source_without_reverse_edge_or_cache(self):
        graph, report = build_schema(self.catalog, ['Company','Equity'])
        self.assertEqual(len(graph['node']), 2)
        self.assertEqual(len(graph['edge']), 1)
        edge = graph['edge'][0]
        self.assertEqual((edge['fromNodeLabel'],edge['toNodeLabel']), ('Company','Equity'))
        source = edge['dataSourceGroup']['externalDataSource']
        self.assertEqual(source['table'], 'equity')
        self.assertIn({'sourceFieldName':'issuer_id','targetFieldName':'source_id'}, source['mappedField'])
        self.assertNotIn('catalog',graph)  # Connection secrets are supplied only at deployment.
        self.assertNotIn('localTable',graph)
        self.assertEqual(report['blockedLinks'], [])

    def test_actor_roles_keep_distinct_edge_identity_on_shared_source(self):
        graph, _ = build_schema(self.catalog, ['Company','Organization','SourceEvent'])
        self.assertEqual(len(graph['edge']), 2)
        for edge in graph['edge']:
            src = edge['dataSourceGroup']['externalDataSource']
            self.assertEqual(src['table'], 'actor_participation')
            self.assertIn({'sourceFieldName':'participation_id','targetFieldName':'key_0'},src['mappedField'])
            self.assertIn({'sourceFieldName':'role_code','targetFieldName':'roleCode'},src['mappedField'])
            self.assertNotIn('"',src['whereClause'])  # PuppyGraph predicate fragments reject SQL quoted identifiers.
        self.assertNotEqual(graph['edge'][0]['dataSourceGroup'], graph['edge'][1]['dataSourceGroup'])

    def test_stale_design_cannot_be_published(self):
        catalog=copy.deepcopy(self.catalog)
        catalog['modelChanged']=True
        with self.assertRaises(ValueError):build_schema(catalog,['Company'])

    def test_money_never_uses_lossy_bolt_float_transport(self):
        graph, report=build_schema(self.catalog,['FinancialMetric'])
        node=graph['node'][0]
        self.assertEqual(next(a['type'] for a in node['attribute'] if a['name']=='value'),'STRING')
        self.assertIn({'sourceFieldName':'value_decimal_text','targetFieldName':'value'},node['dataSourceGroup']['externalDataSource']['mappedField'])
        self.assertEqual(report['valueEncodings']['FinancialMetric']['value']['modelType'],'Decimal')
        broken=copy.deepcopy(self.catalog)
        next(o for o in broken['objects'] if o['id']=='FinancialMetric')['graphValueEncodings']={}
        with self.assertRaisesRegex(ValueError,'lossless'):build_schema(broken,['FinancialMetric'])

    def test_null_endpoint_never_manufactures_a_relationship(self):
        graph,_=build_schema(self.catalog,['Concept'])
        predicate=graph['edge'][0]['dataSourceGroup']['externalDataSource']['whereClause']
        self.assertIn('id IS NOT NULL',predicate)
        self.assertIn('parent_concept_id IS NOT NULL',predicate)
