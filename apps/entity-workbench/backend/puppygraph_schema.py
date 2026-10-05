"""Build credential-free PuppyGraph 1.x mappings from the reviewed view catalogue."""
import re


def build_schema(catalog, object_names):
    objects = {o['id']: o for o in catalog['objects']}
    selected = set(object_names)
    if not selected or not selected <= objects.keys() or catalog['modelChanged']:
        raise ValueError('Select known objects from a current reviewed design')
    tables = {t['id']: t for t in catalog['physicalTables']}
    supported = {'text':'STRING', 'date':'DATE', 'double precision':'DOUBLE',
                 'bigint':'LONG', 'smallint':'SHORT', 'boolean':'BOOLEAN', 'timestamptz':'DATETIME',
                 'text[]':'Array<String>'}

    def field(name, sql_type):
        if sql_type not in supported:
            raise ValueError('Graph type needs verified mapping: ' + sql_type)
        return {'name':name, 'type':supported[sql_type]}

    def source(table, mappings, filters=None, nonnull=()):
        schema, name = table['viewName'].split('.')
        result = {'enabled':True, 'catalog':'ontology', 'schema':schema, 'table':name,
                  'mappedField':[{'sourceFieldName':c, 'targetFieldName':p} for p,c in mappings.items()]}
        clauses = []
        for c in nonnull:
            if not re.fullmatch(r'[a-z][a-z0-9_]*',c):raise ValueError('Invalid endpoint column')
            clauses.append(c+' IS NOT NULL')
        if filters:
            for c, values in filters.items():
                if not re.fullmatch(r'[a-z][a-z0-9_]*',c) or not values or not all(isinstance(v,str) for v in values):
                    raise ValueError('Filter must contain explicit text values')
                clauses.append('('+' OR '.join(c+' = \''+v.replace("'","''")+"'" for v in values)+')')
        if clauses:result['whereClause'] = ' AND '.join(clauses)
        return {'externalDataSource':result}

    nodes, edges, blocked = [], [], []
    for name in sorted(selected):
        obj = objects[name]
        cols = [c for c in obj['columns'] if c.get('property')]
        encodings = obj.get('graphValueEncodings', {})
        column_types = {c['column']:c['type'] for c in obj['columns']}
        properties = {c['property']:c for c in cols}
        for prop, encoding in encodings.items():
            if (prop not in properties or properties[prop]['type'] != 'numeric'
                    or encoding.get('encoding') != 'decimal_text'
                    or column_types.get(encoding.get('column')) != 'text'):
                raise ValueError('Invalid lossless decimal transport: '+name+'.'+prop)
        for c in cols:
            if c['type'] == 'numeric' and encodings.get(c['property'], {}).get('encoding') != 'decimal_text':
                raise ValueError('Decimal requires lossless text transport: '+name+'.'+c['property'])
        nodes.append({'label':name, 'id':[field('id','text')],
                      'attribute':[field(c['property'],'text' if c['property'] in encodings else c['type']) for c in cols],
                      'dataSourceGroup':source(obj,{c['property']:encodings.get(c['property'],{}).get('column',c['column']) for c in cols})})
    for link in catalog['relations']:
        if link['source'] not in selected or link['target'] not in selected:
            continue
        m = link['physicalMapping']
        if m['kind'] == 'blocked':
            blocked.append(link['id'])
            continue
        table = tables[m['source']]
        types = {c['column']:c['type'] for c in table['columns']}
        mappings = {'source_id':m['fromColumn'], 'target_id':m['toColumn'], **m['properties']}
        mappings.update({f'key_{i}':c for i,c in enumerate(m['edgeIdColumns'])})
        edges.append({'label':link['id'], 'fromNodeLabel':link['source'], 'toNodeLabel':link['target'],
                      'id':[field(f'key_{i}',types[c]) for i,c in enumerate(m['edgeIdColumns'])],
                      'fromKey':[field('source_id','text')], 'toKey':[field('target_id','text')],
                      'attribute':[field(p,types[c]) for p,c in mappings.items()],
                      'dataSourceGroup':source(table,mappings,m['filters'],[m['fromColumn'],m['toColumn']])})
    return {'node':nodes,'edge':edges}, {'blockedLinks':blocked, 'objectTypes':sorted(selected),
        'valueEncodings':{n:objects[n]['graphValueEncodings'] for n in sorted(selected) if objects[n].get('graphValueEncodings')}}
