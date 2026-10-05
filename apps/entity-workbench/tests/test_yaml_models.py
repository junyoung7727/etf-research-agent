import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import yaml

from backend.yaml_models import load_models
from backend.modeling import preview_object
from ontology.oms.loader import definition_paths


class SourceModelsTest(unittest.TestCase):
    def test_original_results_and_complete_composite_fk_are_preserved(self):
        from paths import OBJECT_TYPES, DATA, LINK_TYPES, EDGE_ONTOLOGY
        import shutil
        directory = OBJECT_TYPES
        data = DATA
        snapshot = data/'snapshot.sqlite3'
        with closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)) as c:
            meta = json.loads(c.execute('SELECT payload FROM _metadata').fetchone()[0])
        original = json.loads((data/'object-model-stages-1-4.json').read_text(encoding='utf8'))
        model = load_models(directory,meta,EDGE_ONTOLOGY / 'metadata')
        # Expanding the domain design must preserve the existing company identity.
        current=preview_object(snapshot,model,'Company')
        previous=preview_object(snapshot,original,'Company')
        self.assertEqual([r['values']['id'] for r in current['rows']],
                         [r['values']['id'] for r in previous['rows']])
        self.assertEqual(current['stats'],previous['stats'])
        with tempfile.TemporaryDirectory() as tmp:
            for key, path in definition_paths(directory.parent, EDGE_ONTOLOGY / 'metadata').items():
                target = Path(tmp) / key
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(path, target)
            path = Path(tmp)/'object_types'/'Company.yaml'
            doc = yaml.safe_load(path.read_text(encoding='utf8'))
            doc['sourceMapping']['joins'][0]['on'].pop()
            path.write_text(yaml.safe_dump(doc),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'full FK'):
                load_models(Path(tmp)/'object_types',meta)


if __name__ == '__main__':
    unittest.main()
