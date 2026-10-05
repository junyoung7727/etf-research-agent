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
            'valuePolicy': 'typed_null_pending' if pending else 'view_projection' if source.get('kind')=='view_column' else 'identity_encoding' if identity else
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
        proposal.update(id=name, description=d['description'], titleProperty=d['titleProperty'], identity=copy.deepcopy(d['identity']),
            sourceMapping=copy.deepcopy(sm), readiness='proposal', columns=[
                column(n, prop, sm['properties'][n], identity=d['identity'] if n==d['primaryKey'] else None)
                for n, prop in d['properties'].items()] + copy.deepcopy(proposal.get('referenceColumns', [])))
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
    attach_physical_sources(result, plan)
    names = [v['viewName'] for v in result['physicalTables']]
    if len(names)!=len(set(names)) or any(not re.fullmatch(r'(ontology_view|public)\.[a-z][a-z0-9_]{0,62}', n) for n in names):
        raise ValueError('중복되거나 PostgreSQL 식별자 제한을 벗어난 뷰 이름입니다.')
    for view in result['physicalTables']:
        cols = [c['column'] for c in view['columns']]
        if len(cols)!=len(set(cols)):
            raise ValueError('중복 뷰 컬럼: '+view['id'])
    return result


def attach_physical_sources(result, plan):
    """Resolve each logical link without manufacturing one physical view per link."""
    tables = {o['id']: {**copy.deepcopy(o), 'kind': 'object_view', 'primaryKey': ['id']}
              for o in result['objects']}
    for name, source in plan['physicalSources'].items():
        if name in tables:
            raise ValueError('물리 원본 ID 중복: ' + name)
        tables[name] = {**copy.deepcopy(source), 'id': name}
    references = {}
    for relation in result['relations']:
        mapping = relation['physicalMapping']
        kind = mapping['kind']
        if kind == 'blocked':
            if relation['readiness'] != 'blocked':
                raise ValueError('구현 보류 상태 불일치: ' + relation['id'])
            relation['viewName'] = None
            continue
        if kind not in ('object_fk', 'resolved_fk', 'connection_view', 'existing_table'):
            raise ValueError('알 수 없는 물리 매핑: ' + kind)
        source = tables.get(mapping['source'])
        if source is None:
            raise ValueError('관계 원본 없음: ' + relation['id'])
        expected = 'object_view' if kind in ('object_fk', 'resolved_fk') else kind
        if source['kind'] != expected:
            raise ValueError('관계 원본 종류 불일치: ' + relation['id'])
        cols = {c['column']: c for c in source['columns']}
        used = [mapping['fromColumn'], mapping['toColumn'], *mapping['edgeIdColumns'],
                *mapping['filters'], *mapping['properties'].values()]
        if any(c not in cols for c in used) or not mapping['edgeIdColumns']:
            raise ValueError('매핑 컬럼 또는 엣지 식별자 없음: ' + relation['id'])
        relation['viewName'] = source['viewName']
        for column_name, target in ((mapping['fromColumn'], relation['source']),
                                    (mapping['toColumn'], relation['target'])):
            if cols[column_name]['type'] != 'text':
                raise ValueError('객체 ID와 참조 타입 불일치: ' + relation['id'])
            if source['id'] == target and column_name == 'id':
                continue  # The node's own identifier is not a foreign key.
            key = (source['id'], column_name, target)
            reference = references.setdefault(key, {'id': ':'.join(key), 'table': source['id'],
                'column': column_name, 'target': target, 'targetColumn': 'id', 'relationIds': []})
            reference['relationIds'].append(relation['id'])
    for table in tables.values():
        names = {c['column'] for c in table['columns']}
        if not table['primaryKey'] or not set(table['primaryKey']) <= names:
            raise ValueError('물리 원본 식별 키 누락: ' + table['id'])
        for c in table['columns']:
            c['keyRoles'] = (['PK'] if c['column'] in table['primaryKey'] else [])
            c['references'] = [r for r in references.values()
                               if r['table'] == table['id'] and r['column'] == c['column']]
            if c['references']:
                c['keyRoles'].append('FK')
    result['physicalTables'] = list(tables.values())
    result['references'] = list(references.values())


def read_catalog():
    documents = read_definitions(METADATA / 'object_types', EDGE_ONTOLOGY / 'metadata')
    plan = json.loads((APP / 'data/view-design.json').read_text(encoding='utf8'))
    result = build_catalog(documents, plan)
    schema = json.loads((APP / 'data/source-schema.json').read_text(encoding='utf8'))
    fks = {f['constraint']: f for f in schema['foreign_keys']}
    for relation in result['relations']:
        relation['joinContracts'] = [copy.deepcopy(fks[j['constraint']]) for j in relation['sourceMapping'].get('joins', [])]
    return result
