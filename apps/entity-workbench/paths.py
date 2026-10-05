"""Application paths; ontology definition readers receive their paths explicitly."""
import os
import json
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]
DATA = ROOT / 'output/entity-workbench'
FRONTEND = APP / 'frontend'
METADATA = APP / 'ontology/metadata'
OBJECT_TYPES = METADATA / 'object_types'
LINK_TYPES = METADATA / 'link_types'
SOURCE_SCHEMA = APP / 'data/source-schema.json'
LIBRARY_CONFIG = APP / 'data/library.json'
_library = json.loads(LIBRARY_CONFIG.read_text(encoding='utf8')) if LIBRARY_CONFIG.exists() else {}
EDGE_ONTOLOGY = Path(os.environ.get('EDGE_ONTOLOGY_ROOT', _library.get('libraryRoot',
    str(ROOT.parent / 'edge/src/libs/ontology/src/edge_ontology'))))
