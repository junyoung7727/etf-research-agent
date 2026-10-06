"""CQ amounts must be reachable from the same event without losing precision or unknowns."""
import unittest
from paths import APP
from backend.view_design import read_catalog
from backend.puppygraph_schema import build_schema


class MeasurementMappingTests(unittest.TestCase):
    def test_agent_can_discover_measurements_from_event_in_either_direction(self):
        catalog=read_catalog()
        link=next(r for r in catalog['relations'] if r['id']=='EventMeasurement_ForEvent_SourceEvent')
        self.assertEqual(link['source'],'EventMeasurement')
        self.assertEqual(link['target'],'SourceEvent')
        self.assertEqual(link['inverse']['apiName'],'measurements')
        self.assertEqual(link['physicalMapping']['toColumn'],'source_event_id')
        self.assertEqual(link['physicalMapping']['edgeIdColumns'],['id'])

    def test_graph_preserves_decimal_and_interpretation_context(self):
        schema,_=build_schema(read_catalog(),['SourceEvent','EventMeasurement'])
        measurement=next(n for n in schema['node'] if n['label']=='EventMeasurement')
        types={a['name']:a['type'] for a in measurement['attribute']}
        self.assertEqual(types['value'],'STRING')
        self.assertTrue({'reportedText','unit','periodBasis','argumentGroup','parseStatus','availableAt'}<=types.keys())
        mapping={m['targetFieldName']:m['sourceFieldName'] for m in measurement['dataSourceGroup']['externalDataSource']['mappedField']}
        self.assertEqual(mapping['value'],'value_decimal')

    def test_view_neither_selects_latest_nor_turns_unknown_values_into_zero(self):
        sql=(APP/'sql/views/event_measurement.sql').read_text(encoding='utf8').lower()
        self.assertIn('m.source_event_id::text, m.measure_ord::text',sql)
        self.assertIn('m.value::numeric as value',sql)
        self.assertNotIn('coalesce',sql)
        self.assertNotIn('distinct',sql)
        self.assertNotIn('limit',sql)

    def test_participant_group_and_document_assertion_are_queryable_not_hidden_notes(self):
        catalog=read_catalog()
        graph,_=build_schema(catalog,[o['id'] for o in catalog['objects']])
        links={r['label']:r for r in graph['edge']}
        for actor in ('Company','Organization'):
            attrs={a['name']:a['type'] for a in links[actor+'_ParticipatesIn_SourceEvent']['attribute']}
            self.assertEqual(attrs['argumentGroup'],'SHORT')
        for document in ('NewsArticle','Disclosure'):
            attrs={a['name'] for a in links[document+'_DescribesEvent_SourceEvent']['attribute']}
            self.assertTrue({'assertionId','evidenceText','evidenceType'}<=attrs)
