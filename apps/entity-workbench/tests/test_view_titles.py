"""Names are resolved context, never replacements for object identity."""
import copy,json,unittest
from backend.design_models import source_catalog,validate_view_property
from backend.view_design import read_catalog
from backend.puppygraph_viewer import node
from backend.graph_queries import interface_traversal
from backend.interface_types import source_catalog as interfaces
from paths import APP
import yaml
from scripts.publish_view_titles import updated_definition
from paths import EDGE_ONTOLOGY


class ViewTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=read_catalog()
        cls.contract=json.loads((APP/'data/view-display-contracts.json').read_text(encoding='utf-8'))

    def test_each_object_has_a_readable_title_contract_and_keeps_its_id(self):
        self.assertTrue(self.catalog['objects'])
        for obj in self.catalog['objects']:
            self.assertNotEqual(obj['titleProperty'],'id',obj['id'])
            self.assertIn(obj['titleProperty'],{c.get('property') for c in obj['columns']})
            self.assertTrue(obj['identity']['columns'])
        holding=next(o for o in self.catalog['objects'] if o['id']=='ETFHolding')
        self.assertEqual(holding['identity']['columns'],['etf_instrument_id','constituent_instrument_id','trade_date'])

    def test_holding_caption_identifies_the_security_not_just_weight_or_date(self):
        values={'id':'immutable-id','displayTitle':'ETF A / Security B / 2026-10-02',
                'securityName':'Security B','weightRatio':0.2,'tradeDate':'2026-10-02'}
        record=node('ETFHolding',values)
        self.assertEqual(record['id'],'immutable-id')
        self.assertEqual(record['label'],values['displayTitle'])
        self.assertEqual(record['properties']['weightRatio'],0.2)

    def test_existing_index_name_is_not_hidden_behind_an_id(self):
        self.assertEqual(node('MarketIndex',{'id':'index-id','seriesName':'Index name'})['label'],'Index name')

    def test_view_projections_have_source_provenance_without_fake_raw_constraints(self):
        schema=source_catalog()
        for kind,contract in self.contract['objects'].items():
            for name,definition in contract['properties'].items():
                source=contract['mappings'][name]
                validate_view_property(source,definition,schema)
                self.assertTrue((APP/source['sqlFile']).is_file())
                self.assertIsNone(definition['sourceConstraints'])
        source=copy.deepcopy(self.contract['objects']['ETFHolding']['mappings']['displayTitle'])
        source['inputs'][0]['column']='imaginary_name'
        with self.assertRaisesRegex(ValueError,'input'):
            validate_view_property(source,self.contract['objects']['ETFHolding']['properties']['displayTitle'],schema)

    def test_agent_traversal_returns_target_titles_in_the_same_query(self):
        interface=next(i for i in interfaces()['catalog']['interfaces'] if i['name']=='Security')
        query,_=interface_traversal(interface,'heldIn',[{'type':'ETF','id':'etf'}],self.catalog)
        self.assertIn('z.`displayTitle` AS targetTitle',query)
        self.assertIn('z.id AS targetId',query)
        self.assertIn('AS targetType',query)

    def test_publishing_is_idempotent_but_does_not_approve_unrelated_model_changes(self):
        raw=(EDGE_ONTOLOGY/'metadata/object_types/ETFHolding.yaml').read_text(encoding='utf-8')
        addition=self.contract['objects']['ETFHolding'];schema=source_catalog()
        self.assertIsNone(updated_definition(raw,'ETFHolding',addition,schema))
        changed=yaml.safe_load(raw);changed['description']='Unreviewed domain meaning'
        with self.assertRaisesRegex(ValueError,'changed since review'):
            updated_definition(yaml.safe_dump(changed),'ETFHolding',addition,schema)

    def test_publishing_adds_display_fields_to_an_unmodified_original_definition(self):
        addition=self.contract['objects']['ETFHolding']
        doc=yaml.safe_load((EDGE_ONTOLOGY/'metadata/object_types/ETFHolding.yaml').read_text(encoding='utf-8'))
        for prop in addition['properties']:
            del doc['properties'][prop];del doc['sourceMapping']['properties'][prop]
        doc['titleProperty']=addition['previousTitleProperty']
        revised=yaml.safe_load(updated_definition(yaml.safe_dump(doc,sort_keys=False),'ETFHolding',addition,source_catalog()))
        self.assertEqual(revised['titleProperty'],'displayTitle')
        self.assertEqual(revised['identity'],doc['identity'])
        self.assertEqual(revised['properties']['displayTitle'],addition['properties']['displayTitle'])
