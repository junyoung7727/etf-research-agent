import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.design_models import source_catalog
from backend.modeling import preview_object
from backend.yaml_models import load_models


from paths import APP as HERE, DATA, OBJECT_TYPES, LINK_TYPES, EDGE_ONTOLOGY
import shutil



class SemanticModelTests(unittest.TestCase):
    def setUp(self):
        with closing(sqlite3.connect((DATA / 'snapshot.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
            self.meta = json.loads(db.execute('SELECT payload FROM _metadata').fetchone()[0])
        self.model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        self.objects = {obj['id']: obj for obj in self.model['objects']}

    def preview_rows(self, object_id, tables, search=''):
        meta = copy.deepcopy(self.meta)
        catalog = source_catalog()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snapshot.sqlite3'
            with closing(sqlite3.connect(path)) as db, db:
                for table, rows in tables.items():
                    columns = catalog['schema'][table]
                    meta['schema'][table] = columns
                    meta['tables'][table] = {'complete': True}
                    db.execute('CREATE TABLE "' + table + '" (' + ','.join('"' + c['name'] + '" TEXT' for c in columns) + ')')
                    for row in rows:
                        db.execute('INSERT INTO "' + table + '" (' + ','.join('"' + k + '"' for k in row) + ') VALUES (' + ','.join('?' for _ in row) + ')', list(row.values()))
                db.execute('CREATE TABLE _metadata(payload TEXT)')
                db.execute('INSERT INTO _metadata VALUES(?)', (json.dumps(meta),))
            return preview_object(path, self.model, object_id, search)

    def test_annual_report_coverage_is_fy_and_recollections_keep_distinct_snapshot_ids(self):
        shared = dict(corp_code='00123456', fiscal_year='2025', reprt_code='11011',
                      fs_basis='CFS', report_period='Q4', rcept_no='20260301000001')
        result = self.preview_rows('FinancialReportSnapshot', {
            'financial_report_version': [dict(shared, raw_run_id='run-a'), dict(shared, raw_run_id='run-b')]
        }, search='FY')
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual({r['values']['reportCoverage'] for r in result['rows']}, {'FY'})
        self.assertEqual(len({r['values']['id'] for r in result['rows']}), 2)
        self.assertEqual({r['sources']['base']['report_period'] for r in result['rows']}, {'Q4'})

    def test_unreliable_share_does_not_become_a_calculation_method_or_a_reliability_pass(self):
        rows = [dict(fact_id=str(i), share_basis=basis) for i, basis in enumerate(['REPORTED', 'COMPUTED', 'RESCALED', 'UNRELIABLE', None])]
        result = self.preview_rows('ReportedBusinessSegment', {
            'business_segment_fact': rows,
            'disclosure_fact': [dict(fact_id=str(i), is_current='1') for i in range(5)]
        })
        values = {r['values']['id']: r['values'] for r in result['rows']}
        self.assertEqual([values[str(i)]['shareCalculationMethod'] for i in range(5)], ['REPORTED', 'COMPUTED', 'RESCALED', None, None])
        # Parser quality labels stay in source evidence, not domain properties.
        self.assertEqual({r['values']['id']: r['sources']['base']['share_basis'] for r in result['rows']},
                         {str(i): basis for i, basis in enumerate(['REPORTED', 'COMPUTED', 'RESCALED', 'UNRELIABLE', None])})
        for value in values.values():
            self.assertNotIn('isCurrentExtraction', value)
            self.assertNotIn('shareQualityFlag', value)
            self.assertNotIn('isCurrent', value)
            self.assertNotIn('periodStart', value)

    def test_sector_assignment_does_not_expose_market_value_or_listing_details(self):
        sector = self.objects['SecurityIndustryClassification']
        self.assertTrue({'marketCap', 'listingMarket', 'isPrimaryShare'}.isdisjoint(sector['propertyDefinitions']))
        self.assertIn('MarketCapitalization', self.objects)
        self.assertIn('SecurityListingSnapshot', self.objects)
        result = self.preview_rows('MarketCapitalization', {'instrument_classification': [
            dict(instrument_id='security-a', as_of_date='2026-10-01', market_cap='123456789')
        ]})
        row = result['rows'][0]
        self.assertIsNone(row['values']['amount'])
        self.assertEqual(row['sources']['base']['market_cap'], '123456789')
        self.assertNotIn('currencyCode', row['values'])

    def test_participation_is_a_role_bearing_link_not_an_object(self):
        self.assertNotIn('EventParticipation', set(self.objects))
        self.assertNotIn('CompanyEventParticipation', set(self.objects))
        for actor in ('Company', 'Organization'):
            relation = next(r for r in self.model['relations']
                            if r['source'] == actor and r['name'] == 'ParticipatesIn')
            self.assertEqual(relation['target'], 'SourceEvent')
            mapping = relation['sourceMapping']
            self.assertEqual(mapping['identity'], ['event_argument_id'],
                             'Different roles between the same endpoints must remain distinct edges')
            self.assertEqual(mapping['sourceEndpoint'], 'event_argument.entity_id')
            self.assertEqual(mapping['targetEndpoint'], 'event_argument.source_event_id')
            self.assertNotIn('backingObjectType', mapping)
            self.assertEqual(relation['backing']['type'], 'joinTable')
            self.assertEqual(set(relation['linkProperties']), {'roleCode', 'mentionedName', 'argumentGroup'})
            self.assertEqual(mapping['properties']['roleCode']['column'], 'role_code')
            self.assertFalse(relation['linkProperties']['roleCode']['nullable'])
            self.assertTrue(relation['linkProperties']['mentionedName']['nullable'])

    def test_derived_metrics_have_input_links_and_do_not_claim_the_value_is_printed_in_a_report(self):
        links = [r for r in self.model['relations'] if r['source'] == 'FinancialMetric']
        self.assertNotIn('InReport', {r['name'] for r in links})
        inputs = next(r for r in links if r['name'] == 'CalculatedFrom')
        self.assertEqual(inputs['cardinality'], 'N:N')
        self.assertEqual(inputs['target'], 'FinancialMetric')
        self.assertNotEqual(inputs['sourceMapping']['kind'], 'propertyMatch')
        self.assertEqual(next(r for r in links if r['name'] == 'HasReportingContext')['target'], 'FinancialReportSnapshot')


if __name__ == '__main__':
    unittest.main()
