import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import yaml

from backend.modeling import preview_object
from backend.yaml_models import load_models


from paths import APP as HERE, DATA, OBJECT_TYPES, LINK_TYPES, EDGE_ONTOLOGY
from ontology.oms.loader import definition_paths
import shutil



class DesignModelTests(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect((DATA / 'snapshot.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            self.meta = json.loads(db.execute('SELECT payload FROM _metadata').fetchone()[0])

    def test_published_scope_tracks_domain_decisions_not_old_storage_cards(self):
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        objects = {o['id']: o for o in model['objects']}
        self.assertTrue({'EventMeasurement', 'ETFOutlookReport', 'ETFPriceExplanation'} <= objects.keys())
        self.assertNotIn('ReportedSupplyContract', objects)
        self.assertNotIn('ETFHoldingCollectionStatus', objects)
        internal = {'dataVersion', 'rawRunId', 'collectionRunId', 'parserVersion',
                    'isCurrentExtraction', 'completeness', 'threadKey', 'dedupClusterId',
                    'shareQualityFlag', 'status'}
        for obj in objects.values():
            self.assertTrue(internal.isdisjoint(obj['propertyDefinitions']), obj['id'])
        self.assertIn('EventThread', objects)
        self.assertIn('NewsArticle', objects)
        self.assertNotIn('EventParticipation', set(objects))
        self.assertNotIn('confidenceLevel', {p['id'] for p in objects['SourceEvent']['properties']})
        # A potentially broken join must not weaken the intended article contract.
        self.assertFalse(objects['NewsArticle']['propertyDefinitions']['sourceCode']['nullable'])
        self.assertTrue(objects['NewsArticle']['propertyDefinitions']['title']['nullable'])
        self.assertEqual(objects['EventThread']['propertyDefinitions']['lastStateAt']['mappingStatus'], 'needsCorrection')
        reports = [r for r in model['relations'] if r['name'] == 'DescribesEvent']
        self.assertEqual({r['source'] for r in reports}, {'NewsArticle', 'Disclosure'})
        for rel in reports:
            self.assertEqual(set(rel['linkProperties']), {'assertionId', 'evidenceType', 'evidenceText'})
            self.assertEqual(set(rel['sourceMapping'].get('evidenceFields', {})), {'extractionConfidence'} if rel['source'] == 'NewsArticle' else set())

    def test_source_constraints_are_verified_and_composite_fk_is_not_shortened(self):
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        company = next(o for o in model['objects'] if o['id'] == 'Company')
        constraints = company['propertyDefinitions']['id']['sourceConstraints']
        self.assertFalse(constraints['nullable'])
        self.assertEqual(constraints['primaryKey'], ['actor_id'])
        self.assertEqual(constraints['foreignKeys'][0]['columns'], ['actor_id', 'actor_type'])
        with tempfile.TemporaryDirectory() as tmp:
            for key, source in definition_paths(OBJECT_TYPES.parent, EDGE_ONTOLOGY / 'metadata').items():
                target = Path(tmp) / key
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(source, target)
            file = Path(tmp) / 'object_types' / 'Company.yaml'
            doc = yaml.safe_load(file.read_text(encoding='utf-8'))
            doc['properties']['id']['sourceConstraints']['nullable'] = True
            file.write_text(yaml.safe_dump(doc), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'constraint'):
                load_models(Path(tmp)/'object_types', self.meta)

    def test_composite_identity_preserves_each_holding_date(self):
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        result = preview_object(DATA / 'snapshot.sqlite3', model, 'ETFHolding')
        self.assertGreater(result['stats']['joined_rows'], 0)
        self.assertEqual(result['stats']['duplicate_ids'], 0)
        row = result['rows'][0]
        self.assertEqual(json.loads(row['values']['id']), [str(row['sources']['base'][c]) for c in
                         ['etf_instrument_id', 'constituent_instrument_id', 'trade_date']])

    def test_uncaptured_table_is_not_reported_as_empty_database(self):
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        with self.assertRaisesRegex(ValueError, '스냅샷'):
            preview_object(DATA / 'snapshot.sqlite3', model, 'EventThread')

    def test_foundry_style_metadata_keeps_reverse_traversal_without_duplicate_links(self):
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        objects = {o['id']: o for o in model['objects']}
        for obj in objects.values():
            self.assertNotIn('semanticContract', obj)
            self.assertIn(obj['titleProperty'], obj['propertyDefinitions'])
            self.assertEqual(obj['primaryKey'], 'id')
            self.assertEqual(obj['status'], 'experimental')
            self.assertTrue(obj['displayName'])
        relations = {r['id']: r for r in model['relations']}
        self.assertTrue({'EventMeasurement_ForEvent_SourceEvent', 'ETFOutlookReport_ForETF_ETF',
                         'ETFPriceExplanation_ForETF_ETF'} <= relations.keys())
        participation = relations['Company_ParticipatesIn_SourceEvent']
        self.assertEqual(participation['cardinality'], 'N:N')
        self.assertEqual(participation['mappingStatus'], 'defined')
        self.assertNotEqual(participation['sourceMapping']['kind'], 'propertyMatch')
        self.assertEqual(set(participation['linkProperties']), {'roleCode', 'mentionedName', 'argumentGroup'})
        self.assertEqual(participation['backing']['type'], 'joinTable')
        disclosure = relations['Company_HasDisclosure_Disclosure']
        self.assertEqual(disclosure['inverse']['apiName'], 'forCompany')
        self.assertNotIn('Disclosure_ForCompany_Company', relations)
        self.assertEqual(relations['Company_Issues_Equity']['inverse']['apiName'], 'issuedBy')
        self.assertNotIn('Equity_IssuedBy_Company', relations)
        # Both traversal directions must be addressable without API-name collisions.
        names = {key: set() for key in objects}
        for rel in relations.values():
            self.assertNotIn('semanticContract', rel)
            for owner, api in ((rel['source'], rel['apiName']), (rel['target'], rel['inverse']['apiName'])):
                self.assertNotIn(api, names[owner], (owner, api))
                names[owner].add(api)
        thread = objects['EventThread']
        self.assertEqual(thread['propertyDefinitions']['currentStage']['mappingStatus'], 'needsCorrection')
        from backend.modeling import object_sql
        from backend.design_models import model_metadata
        _, _, values, _, _ = object_sql(thread, model_metadata(self.meta))
        self.assertEqual(values['currentStage'], 'NULL')

    def test_financial_values_expose_time_basis_and_calculation_inputs(self):
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        objects = {o['id']: o for o in model['objects']}
        for name in ('FinancialReportSnapshot', 'FinancialMetric'):
            mapping = objects[name]['sourceMapping']['properties']
            self.assertEqual(mapping['receivedAt']['column'], 'received_at')
            self.assertEqual(mapping['availabilityBasis']['column'], 'availability_basis')
        self.assertEqual(objects['FinancialMetric']['sourceMapping']['properties']['calculationInputs']['column'], 'inputs')

    def test_ambiguous_traversal_names_and_missing_title_keys_are_rejected(self):
        from backend.design_models import validate_ontology_metadata
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        broken = copy.deepcopy(model)
        broken['objects'][0]['titleProperty'] = 'missingProperty'
        with self.assertRaisesRegex(ValueError, 'key property'):
            validate_ontology_metadata(broken)
        broken = copy.deepcopy(model)
        links = [r for r in broken['relations'] if r['source'] == 'Company']
        links[1]['apiName'] = links[0]['apiName']
        with self.assertRaisesRegex(ValueError, 'duplicate link API'):
            validate_ontology_metadata(broken)

    def test_daily_bar_keeps_zero_volume_and_does_not_invent_unmapped_prices(self):
        from backend.design_models import source_catalog
        model = load_models(OBJECT_TYPES, self.meta, EDGE_ONTOLOGY / 'metadata')
        price = next(o for o in model['objects'] if o['id'] == 'DailyBar')
        for field in ('openPrice', 'highPrice', 'lowPrice', 'closePrice', 'volume', 'turnoverValue'):
            self.assertIn(field, price['propertyDefinitions'])
        for field in ('openPrice', 'highPrice', 'lowPrice'):
            definition = price['propertyDefinitions'][field]
            self.assertEqual(definition['mappingStatus'], 'unmapped')
            self.assertNotIn('sourceConstraints', definition)
        self.assertEqual(price['sourceMapping']['properties']['volume']['column'], 'volume')
        # A zero-volume day is a known observation. An unreported trading value
        # remains NULL, while prices with no backing column have no object value.
        meta = copy.deepcopy(self.meta)
        columns = source_catalog()['schema']['price_daily']
        meta['schema']['price_daily'] = columns
        meta['tables']['price_daily'] = {'complete': True}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'object_types').mkdir()
            shutil.copytree(LINK_TYPES,Path(tmp)/'link_types')
            snapshot = Path(tmp) / 'snapshot.sqlite3'
            with closing(sqlite3.connect(snapshot)) as db, db:
                db.execute('CREATE TABLE _metadata(payload TEXT)')
                db.execute('INSERT INTO _metadata VALUES(?)', (json.dumps(meta),))
                fields = ','.join('"'+c['name']+'" '+('INTEGER' if c['name']=='volume' else 'TEXT') for c in columns)
                db.execute('CREATE TABLE price_daily('+fields+')')
                db.execute('INSERT INTO price_daily(instrument_id,trade_date,close_price,volume,turnover_value) VALUES(?,?,?,?,?)',
                           ('test-security','2026-10-01','12500',0,None))
            row = preview_object(snapshot, model, 'DailyBar')['rows'][0]['values']
            self.assertEqual(row['volume'], 0)
            self.assertIsNone(row['turnoverValue'])
            self.assertEqual(row['closePrice'], '12500')
            for field in ('openPrice', 'highPrice', 'lowPrice'):
                self.assertNotIn(field, row)


if __name__ == '__main__':
    unittest.main()
