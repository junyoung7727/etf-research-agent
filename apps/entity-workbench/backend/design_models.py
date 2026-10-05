"""Bind domain definitions to a captured schema without requiring captured data rows."""
import copy
import json
import re
from pathlib import Path
from paths import SOURCE_SCHEMA


def source_catalog():
    return json.loads(SOURCE_SCHEMA.read_text(encoding='utf-8'))


def model_metadata(snapshot):
    catalog = source_catalog()
    meta = copy.deepcopy(snapshot)
    for table, columns in catalog['schema'].items():
        meta['schema'].setdefault(table, columns)
    known = {fk.get('constraint') for fk in meta['foreign_keys']}
    meta['foreign_keys'] += [fk for fk in catalog['foreign_keys'] if fk['constraint'] not in known]
    return meta


def column_constraints(catalog, table, column):
    field = next(c for c in catalog['schema'][table] if c['name'] == column)
    pk = catalog['primary_keys'].get(table, [])
    return dict(nullable=field['nullable'], primaryKey=pk if column in pk else [],
                foreignKeys=[fk for fk in catalog['foreign_keys'] if fk['table'] == table and column in fk['columns']])


def validate_view_property(source, definition, catalog):
    """A view projection is not a column or constraint in the captured raw tables."""
    if (source.get('schema') != 'ontology_view' or
            any(not re.fullmatch(r'[a-z][a-z0-9_]*', source.get(k, '')) for k in ('table','column')) or
            source.get('sqlFile') != 'sql/views/'+source['table']+'.sql' or
            definition.get('sourceConstraints') is not None or
            definition.get('mappingStatus') != 'ready' or
            not source.get('inputs')):
        raise ValueError('Invalid view projection contract')
    for item in source['inputs']:
        if item.get('schema') != 'public' or item.get('column') not in {c['name'] for c in catalog['schema'].get(item.get('table'), [])}:
            raise ValueError('Unknown view projection input')


def compile_models(documents, snapshot):
    from backend.modeling import validate_model
    catalog = source_catalog()
    meta = model_metadata(snapshot)
    model = {'objects': [], 'relations': []}
    for path, doc, raw in documents:
        if doc['formatVersion'] != 2:
            raise ValueError('Do not mix model format versions')
        sm = doc['sourceMapping']
        if sm['connection'] != 'aws_work' or sm['schema'] != 'public':
            raise ValueError('Unknown source connection/schema')
        table = sm['baseTable']
        keys = doc['identity']['columns']
        if keys != catalog['primary_keys'][table]:
            raise ValueError('Identity must preserve the complete source primary key')
        aliases = {'base': table}
        joins = []
        for join in sm['joins']:
            matches = [(i, fk) for i, fk in enumerate(meta['foreign_keys']) if fk.get('constraint') == join['constraint']]
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous FK constraint')
            i, fk = matches[0]
            expected = [{'source': a, 'target': b} for a, b in zip(fk['columns'], fk['target_columns'])]
            if (join['joinType'] != 'left' or aliases.get(join['from']) != fk['table'] or
                    join['table'] != fk['target_table'] or join['on'] != expected):
                raise ValueError('Source mapping disagrees with full FK constraint')
            aliases[join['alias']] = join['table']
            joins.append(dict(id=join['alias'], **{'from': join['from']}, fk=i, reverse=False, definition=fk))
        if set(doc['properties']) != set(sm['properties']):
            raise ValueError('Every property requires an explicit source mapping')
        properties = []
        view_properties = []
        for name, definition in doc['properties'].items():
            if type(definition['nullable']) is not bool:
                raise ValueError('A property must declare its model nullability')
            source = sm['properties'][name]
            if source.get('kind') == 'view_column':
                validate_view_property(source, definition, catalog)
                view_properties.append(name)
                continue  # The local SQLite preview contains raw tables, not live views.
            if source.get('kind') == 'unmapped':
                if (name == 'id' or definition.get('mappingStatus') != 'unmapped' or
                        not definition.get('dataType') or definition.get('sourceConstraints') is not None or
                        any(k in source for k in ('alias', 'table', 'column'))):
                    raise ValueError('An unmapped property must not claim a source column or constraint')
                # Preserve the intended property in the definition. It has no
                # value in the source preview until a real mapping is provided.
                continue
            if 'lookupProperty' in source:
                base = sm['properties'][source['lookupProperty']]
                properties.append(dict(id=name, label=definition['label'], source=base['alias'], column=base['column'],
                                       lookup=source, definition=definition))
                continue
            if aliases.get(source['alias']) != source['table']:
                raise ValueError('Source table/alias mismatch')
            expected = column_constraints(catalog, source['table'], source['column'])
            if definition.get('sourceConstraints') != expected:
                raise ValueError('Source constraint metadata disagrees with captured PostgreSQL catalog: '+name)
            col = next(c for c in catalog['schema'][source['table']] if c['name'] == source['column'])
            if not (name == 'id' and len(keys) > 1) and definition['sourceDataType'] != col['type']:
                raise ValueError('Source datatype changed: '+name)
            if name != 'id':
                properties.append(dict(id=name, label=definition['label'], source=source['alias'], column=source['column'],
                                       definition=definition, mappingStatus=definition['mappingStatus']))
                if 'valueMapping' in source:
                    mapping = source['valueMapping']
                    if (not isinstance(mapping, dict) or not mapping or
                            any(not isinstance(k, str) or (v is not None and not isinstance(v, str))
                                for k, v in mapping.items())):
                        raise ValueError('Value mappings require string keys and string or NULL values')
                    properties[-1]['valueMapping'] = copy.deepcopy(mapping)
        missing = sorted(set(aliases.values()) - set(snapshot['schema']))
        obj = dict(id=doc['name'], label=doc['label'], note=doc['description'], table=table,
                   key=keys[0] if len(keys) == 1 else keys, joins=joins, filters=sm['filters'], properties=properties,
                   sourceMapping=sm, propertyDefinitions=doc['properties'], identity=doc['identity'],
                   sourceConstraints=doc['sourceConstraints'], group=doc['group'], dataIssues=doc.get('dataIssues', []),
                   implementedInterfaces=doc.get('implementedInterfaces', []),
                   apiName=doc['apiName'], displayName=doc['displayName'], pluralDisplayName=doc['pluralDisplayName'],
                   primaryKey=doc['primaryKey'], titleProperty=doc['titleProperty'], status=doc['status'], visibility=doc['visibility'],
                   definitionYaml=raw, sourceFile=path.name, formatVersion=2, definitionSources=doc.get('_definitionSources', {}),
                   preview={'available':not missing,'missingTables':missing,'reason':'원본 테이블이 현재 로컬 스냅샷에 수집되지 않았습니다.' if missing else ''})
        obj['preview']['viewOnlyProperties'] = view_properties
        model['objects'].append(obj)
        for link in doc['links']:
            mapping = copy.deepcopy(link['sourceMapping'])
            for join in mapping.get('joins', []):
                join['definition'] = next(fk for fk in catalog['foreign_keys'] if fk['constraint'] == join['constraint'])
            model['relations'].append(dict(id=f"{doc['name']}_{link['name']}_{link['target']}", name=link['name'], label=link['label'],
                source=doc['name'], target=link['target'], source_property=link['sourceProperty'], target_property=link['targetProperty'],
                cardinality=link['cardinality'], note=link['description'], sourceMapping=mapping,
                apiName=link['apiName'], displayName=link['displayName'], pluralDisplayName=link['pluralDisplayName'],
                inverse=link['inverse'], backing=link['backing'], status=link['status'], mappingStatus=link['mappingStatus']))
            if 'linkProperties' in link:
                fields = link['linkProperties']
                if set(fields) != set(mapping.get('properties', {})):
                    raise ValueError('Every link property requires an explicit source mapping')
                for name, definition in fields.items():
                    source = mapping['properties'][name]
                    expected = column_constraints(catalog, source['table'], source['column'])
                    column = next(c for c in catalog['schema'][source['table']] if c['name'] == source['column'])
                    if (source['table'] != mapping['baseTable'] or
                            definition['sourceConstraints'] != expected or
                            definition['sourceDataType'] != column['type'] or
                            type(definition['nullable']) is not bool):
                        raise ValueError('Link property source contract mismatch: ' + name)
                model['relations'][-1]['linkProperties'] = copy.deepcopy(fields)
    validate_ontology_metadata(model)
    return validate_model(model, meta)


def validate_ontology_metadata(model):
    """Check the local subset of Foundry metadata without claiming import compatibility."""
    import re
    names = {o['id']: set() for o in model['objects']}
    statuses = {'active', 'experimental', 'deprecated'}
    for obj in model['objects']:
        if obj['status'] not in statuses or obj['primaryKey'] != 'id' or obj['titleProperty'] not in obj['propertyDefinitions']:
            raise ValueError('Invalid ontology status or key property')
        for prop in obj['propertyDefinitions'].values():
            if prop['status'] not in statuses or not re.fullmatch('[a-z][A-Za-z0-9]{0,99}', prop['apiName']):
                raise ValueError('Invalid property API name or status')
    for rel in model['relations']:
        if rel['status'] not in statuses:
            raise ValueError('Invalid link type status')
        for owner, api in ((rel['source'], rel['apiName']), (rel['target'], rel['inverse']['apiName'])):
            if not re.fullmatch('[a-z][A-Za-z0-9]{0,99}', api) or api in names[owner]:
                raise ValueError('Invalid or duplicate link API name: '+owner+'.'+api)
            names[owner].add(api)
