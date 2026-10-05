"""Publish source-mapped YAML definitions to the existing local preview store."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import yaml
from paths import OBJECT_TYPES, DATA, EDGE_ONTOLOGY
from ontology.oms.loader import read_definitions

from backend.modeling import read_model, save_model, validate_model


def load_models(directory, meta, library=None):
    documents = read_definitions(directory, library)
    if any(doc.get('formatVersion') == 2 for _, doc, _ in documents):
        from backend.design_models import compile_models
        return compile_models(documents, meta)
    model = {'objects': [], 'relations': []}
    for path, doc, raw in documents:
        if doc['formatVersion'] != 1:
            raise ValueError('Unsupported model format')
        sm = doc['sourceMapping']
        if sm['connection'] != 'aws_work' or sm['schema'] != 'public':
            raise ValueError('The preview snapshot only represents aws_work.public')
        tables = {'base': sm['baseTable']}
        joins = []
        for j in sm['joins']:
            matches = [(i, f) for i, f in enumerate(meta['foreign_keys'])
                       if f['constraint'] == j['constraint']]
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous FK: ' + j['constraint'])
            i, fk = matches[0]
            if (j['joinType'] != 'left' or tables[j['from']] != fk['table']
                    or j['table'] != fk['target_table']
                    or j['on'] != [dict(source=a, target=b) for a, b in
                                   zip(fk['columns'], fk['target_columns'])]):
                raise ValueError('Source mapping disagrees with full FK: ' + j['constraint'])
            joins.append(dict(id=j['alias'], **{'from': j['from']}, fk=i,
                              reverse=False, definition=fk))
            tables[j['alias']] = j['table']
        if set(sm['properties']) != set(doc['properties']):
            raise ValueError('Every property must have exactly one source mapping')
        for name, source in sm['properties'].items():
            if tables.get(source['alias']) != source['table']:
                raise ValueError('Unknown source alias/table: ' + name)
            if source['column'] not in {c['name'] for c in meta['schema'][source['table']]}:
                raise ValueError('Unknown source column: ' + name)
        identity = sm['properties'][doc['primaryKey']]
        if doc['primaryKey'] != 'id' or identity['alias'] != 'base':
            raise ValueError('The current preview requires a base-table id')
        obj = dict(id=doc['name'], label=doc['label'], note=doc['description'],
                   table=sm['baseTable'], key=identity['column'], joins=joins,
                   filters=sm['filters'], sourceMapping=sm, properties=[],
                   definitionYaml=path.read_text(encoding='utf8'), sourceFile=path.name)
        for name, prop in doc['properties'].items():
            source = sm['properties'][name]
            column = next(c for c in meta['schema'][source['table']] if c['name'] == source['column'])
            if prop['sourceDataType'] != column['type']:
                raise ValueError('Source datatype changed: ' + name)
            if name != 'id':
                obj['properties'].append(dict(id=name, label=prop['label'],
                                              source=source['alias'], column=source['column']))
        for link in doc['links']:
            model['relations'].append(dict(id=link['name'], label=link['label'],
                source=doc['name'], target=link['target'], source_property=link['sourceProperty'],
                target_property=link['targetProperty'], cardinality=link['cardinality'], note=link['description']))
        model['objects'].append(obj)
    if not model['objects']:
        raise ValueError('No YAML models found')
    return validate_model(model, meta)


def publish():
    directory = OBJECT_TYPES
    data = DATA
    with closing(sqlite3.connect((data/'snapshot.sqlite3').as_uri()+'?mode=ro', uri=True)) as c:
        meta = json.loads(c.execute('SELECT payload FROM _metadata').fetchone()[0])
    model = load_models(directory, meta, EDGE_ONTOLOGY / 'metadata')
    previous = read_model(data/'models.sqlite3')
    # Layout is presentation state, not part of the YAML ontology contract.
    # New domain definitions use the viewer's automatic group layout.
    model['objects'].sort(key=lambda o: (o.get('group', ''), o['id']))
    saved = save_model(data/'models.sqlite3', model, previous['revision'], meta)
    (data/'published-model.json').write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding='utf8')
    print('Published YAML models, revision', saved['revision'])
