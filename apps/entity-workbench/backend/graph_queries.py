"""Deterministic interface traversal across concrete PuppyGraph labels."""
import re


def name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',value):
        raise ValueError('Invalid graph identifier')
    return '`'+value+'`'


def interface_traversal(interface, link_name, typed_ids, catalog, link_filters=None):
    """One UNION ALL query for a bounded set; preserve concrete and edge identity."""
    if link_name not in interface['links'] or interface['links'][link_name]['target']['kind']!='object':
        raise ValueError('An object-target interface link is required')
    if not isinstance(typed_ids,list) or len(typed_ids)>1000:
        raise ValueError('Provide at most 1000 typed object IDs')
    implementations=interface['implementations']
    selected={t:[] for t in implementations}
    for item in typed_ids:
        if (not isinstance(item,dict) or set(item)!={'type','id'} or item['type'] not in selected
                or not isinstance(item['id'],str) or not item['id']):
            raise ValueError('Each ID requires a known concrete type and nonempty string id')
        if item['id'] not in selected[item['type']]:selected[item['type']].append(item['id'])
    links={r['id']:r for r in catalog['relations']}
    mappings=[links[i['links'][link_name]['linkType']]['physicalMapping']
              for i in implementations.values() if link_name in i['links']]
    property_names=sorted({p for m in mappings for p in m.get('properties',{})})
    key_count=max((len(m.get('edgeIdColumns',[])) for m in mappings),default=0)
    params={};branches=[]
    for index,(object_type,impl) in enumerate(implementations.items()):
        contract=impl['links'].get(link_name)
        if not contract:
            if selected[object_type]:raise ValueError('Selected object does not implement this link')
            continue
        link=links[contract['linkType']];m=link['physicalMapping']
        if m['kind']=='blocked':raise ValueError('Requested link is not implemented')
        target=link['target'] if contract['direction']=='forward' else link['source']
        node='(a:'+name(object_type)+')';end='(z:'+name(target)+')'
        pattern=node+('-[r:'+name(link['id'])+']->' if contract['direction']=='forward' else '<-[r:'+name(link['id'])+']-')+end
        key=f'ids_{index}';params[key]=selected[object_type]
        conditions=['a.'+name(impl['properties']['id'])+' IN $'+key]
        for i,(prop,value) in enumerate((link_filters or {}).items()):
            if prop not in m['properties']:raise ValueError('Unknown relationship filter: '+prop)
            param=f'filter_{index}_{i}';params[param]=value
            conditions.append('r.'+name(prop)+' = $'+param)
        # PuppyGraph 1.13 rejects UNION on maps/lists. Preserve all fields as scalar columns.
        props=[('a.'+name(impl['properties'][p]))+' AS '+name('object_'+p) for p in interface['properties'] if p!='id']
        edge_props=[('r.'+name(p) if p in m['properties'] else 'NULL')+' AS '+name('link_'+p) for p in property_names]
        edge_keys=[('r.'+name(f'key_{i}') if i<len(m['edgeIdColumns']) else 'NULL')+' AS '+name(f'linkKey{i}') for i in range(key_count)]
        branches.append('MATCH '+pattern+' WHERE '+' AND '.join(conditions)+
            " RETURN '"+object_type+"' AS objectType, a."+name(impl['properties']['id'])+
            " AS objectId, '"+target+"' AS targetType, z.id AS targetId, '"+link['id']+
            "' AS linkType, "+', '.join(props+edge_keys+edge_props))
    if not branches:raise ValueError('No concrete link mappings')
    return ' UNION ALL '.join(branches),params
