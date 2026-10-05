"""Read-only view proposals attached to source definitions, never executable DDL."""
import copy
import hashlib
import json
import re

from paths import APP, METADATA, EDGE_ONTOLOGY
from ontology.oms.loader import read_definitions


def snake(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', '_', name).lower()


def pg_type(definition):
    types = {'String': 'text', 'String[]': 'text[]', 'Timestamp': 'timestamptz',
             'Date': 'date', 'Decimal': 'numeric', 'Long': 'bigint',
             'Short': 'smallint', 'Double': 'double precision', 'Boolean': 'boolean'}
    return types[definition['dataType']]


def column(name, definition, source, *, identity=None):
    status = definition.get('mappingStatus', 'ready')
    pending = status in ('unmapped', 'needsCorrection')
    return {'property': name, 'column': snake(name), 'type': 'text' if identity else pg_type(definition),
            'description': definition.get('description', ''), 'source': copy.deepcopy(source),
            'modelNullable': definition.get('nullable', True), 'viewNullable': True if pending else definition.get('nullable', True),
            'mappingStatus': status,
            'valuePolicy': 'typed_null_pending' if pending else 'identity_encoding' if identity else
                           'explicit_transform' if any(k in source for k in ('valueMapping', 'lookupProperty', 'valueEncoding')) else 'source_value',
            'identity': identity}


def build_catalog(documents, plan):
    definitions = {d['name']: d for _, d, _ in documents}
    relations = {name: (d, link) for d in definitions.values() for name, link in zip(d['linkTypes'], d['links'])}
    if set(definitions) != set(plan['objects']) or set(relations) != set(plan['relations']):
        raise ValueError('모델 타입 목록과 뷰 설계가 다릅니다. 새 타입 또는 삭제된 타입의 설계를 먼저 갱신하세요.')
    hashes = {key: hashlib.sha256(raw.encode('utf8')).hexdigest()
              for d in definitions.values() for key, raw in d['_definitionSources'].items()
              if not key.startswith('interface_types/')}
    result = {k: copy.deepcopy(plan[k]) for k in ('revision', 'designedAt', 'status', 'rules', 'issues')}
    result.update(modelChanged=hashes != plan['definitionHashes'], objects=[], relations=[])
    for name, d in definitions.items():
        sm = d['sourceMapping']
        proposal = copy.deepcopy(plan['objects'][name])
        proposal.update(id=name, description=d['description'], identity=copy.deepcopy(d['identity']),
            sourceMapping=copy.deepcopy(sm), readiness='proposal', columns=[
                column(n, prop, sm['properties'][n], identity=d['identity'] if n==d['primaryKey'] else None)
                for n, prop in d['properties'].items()])
        result['objects'].append(proposal)
    for name, (owner, d) in relations.items():
        sm = d['sourceMapping']
        proposal = copy.deepcopy(plan['relations'][name])
        proposal.update(id=name, description=d['description'], source=owner['name'], target=d['target'],
            inverse=copy.deepcopy(d['inverse']), cardinality=d['cardinality'], sourceMapping=copy.deepcopy(sm),
            match={'sourceProperty': d['sourceProperty'], 'targetProperty': d['targetProperty']},
            sourceView=plan['objects'][owner['name']]['viewName'], targetView=plan['objects'][d['target']]['viewName'],
            columns=[{'column': n, 'type': 'text', 'description': desc, 'viewNullable': False} for n, desc in (
                ('edge_id', '현재 관계 타입 안에서 유일한 관계 기록 ID. 원본 키 또는 명시된 객체 쌍으로 구성한다.'),
                ('source_id', '출발 객체 뷰의 id와 같은 값. 출발 타입과 함께 해석한다.'),
                ('target_id', '도착 객체 뷰의 id와 같은 값. 도착 타입과 함께 해석한다.'))])
        for n, prop in d.get('linkProperties', {}).items():
            proposal['columns'].append(column(n, prop, sm['properties'][n]))
        for n, evidence in sm.get('evidenceFields', {}).items():
            proposal['columns'].append({'column': snake(n), 'type': 'numeric' if n=='extractionConfidence' else 'text',
                'description': evidence['description'], 'source': evidence['source'], 'viewNullable': True,
                'valuePolicy': 'source_value'})
        result['relations'].append(proposal)
    names = [v['viewName'] for v in result['objects'] + result['relations']]
    if len(names)!=len(set(names)) or any(not re.fullmatch(r'ontology_view\.[a-z][a-z0-9_]{0,62}', n) for n in names):
        raise ValueError('중복되거나 PostgreSQL 식별자 제한을 벗어난 뷰 이름입니다.')
    for view in result['objects']+result['relations']:
        cols = [c['column'] for c in view['columns']]
        if len(cols)!=len(set(cols)):
            raise ValueError('중복 뷰 컬럼: '+view['id'])
    return result


def read_catalog():
    documents = read_definitions(METADATA / 'object_types', EDGE_ONTOLOGY / 'metadata')
    plan = json.loads((APP / 'data/view-design.json').read_text(encoding='utf8'))
    result = build_catalog(documents, plan)
    schema = json.loads((APP / 'data/source-schema.json').read_text(encoding='utf8'))
    fks = {f['constraint']: f for f in schema['foreign_keys']}
    for relation in result['relations']:
        relation['joinContracts'] = [copy.deepcopy(fks[j['constraint']]) for j in relation['sourceMapping'].get('joins', [])]
    return result
