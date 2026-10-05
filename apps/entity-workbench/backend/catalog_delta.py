"""Store only edited fields; source provenance is always read from the library."""
import copy


def difference(catalog, baseline):
    originals = {t['id']: t for t in baseline['valueTypes']}
    changes = []
    for definition in catalog['valueTypes']:
        original = originals.get(definition['id'], {})
        change = {'id': definition['id']}
        for key in ('description', 'baseType', 'usedBy'):
            if definition.get(key) != original.get(key):
                change[key] = copy.deepcopy(definition[key])
        values = {v['code']: v for v in original.get('values', [])}
        edits = []
        for value in definition['values']:
            before = values.get(value['code'], {})
            edit = {'code': value['code']}
            for key in ('description', 'group', 'rule'):
                if key in value and value[key] != before.get(key):
                    edit[key] = copy.deepcopy(value[key])
            if len(edit) > 1:
                edits.append(edit)
        if edits:
            change['values'] = edits
        if len(change) > 1:
            changes.append(change)
    return {'formatVersion': 2, 'valueTypes': changes}


def apply_difference(baseline, delta):
    result = copy.deepcopy(baseline)
    types = {t['id']: t for t in result['valueTypes']}
    for change in delta['valueTypes']:
        name = change['id']
        if name not in types:
            types[name] = dict(id=name, description='', baseType='String', usedBy=[], values=[])
            result['valueTypes'].append(types[name])
        target = types[name]
        for key in ('description', 'baseType', 'usedBy'):
            if key in change:
                target[key] = copy.deepcopy(change[key])
        values = {v['code']: v for v in target['values']}
        for edit in change.get('values', []):
            if edit['code'] not in values:
                values[edit['code']] = dict(code=edit['code'], description='', group='')
                target['values'].append(values[edit['code']])
            values[edit['code']].update(copy.deepcopy(edit))
    return result
