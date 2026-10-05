import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import yaml

from paths import OBJECT_TYPES, DATA, EDGE_ONTOLOGY
from ontology.oms.loader import read_definitions
from backend.yaml_models import load_models


class LayoutMigrationTest(unittest.TestCase):
    def test_portable_definitions_preserve_every_model_and_link(self):
        with sqlite3.connect(DATA / 'snapshot.sqlite3') as db:
            meta = json.loads(db.execute('SELECT payload FROM _metadata').fetchone()[0])
        # Compare the same domain model in inline and split layouts. The historical
        # migration snapshot must not prohibit later intentional domain changes.
        documents = read_definitions(OBJECT_TYPES, EDGE_ONTOLOGY / 'metadata')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'object_types'
            directory.mkdir()
            for path, doc, _ in documents:
                for key, raw in doc.get('_definitionSources', {}).items():
                    if key.startswith('interface_types/'):
                        interface = Path(tmp) / key
                        interface.parent.mkdir(exist_ok=True)
                        interface.write_text(raw, encoding='utf8')
                doc.pop('linkTypes', None)
                doc.pop('_definitionSources', None)
                (directory / path.name).write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf8')
            before = load_models(directory, meta)
        after = load_models(OBJECT_TYPES, meta, EDGE_ONTOLOGY / 'metadata')
        for model in (before, after):
            for obj in model['objects']:
                for key in ('definitionYaml', 'definitionSources'):
                    obj.pop(key, None)
        self.assertEqual(before, after)
        self.assertEqual(sum(len(doc['links']) for _, doc, _ in read_definitions(OBJECT_TYPES, EDGE_ONTOLOGY / 'metadata')), len(before['relations']))


if __name__ == '__main__':
    unittest.main()
