"""Validate interface contracts against concrete object and link definitions."""
import re

TYPES = ('String', 'String[]', 'Timestamp', 'Date', 'Decimal', 'Long', 'Short', 'Double', 'Boolean')


def validate_interfaces(interfaces, objects, links):
    def fail(message):
        raise ValueError(message)

    def text(value, where):
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            fail(where + ': 비어 있지 않은 설명이 필요합니다.')

    def name(value):
        return isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,99}', value)

    def fields(value, required, where):
        if not isinstance(value, dict) or set(value) != set(required):
            fail(where + ': 필드 구성을 확인하세요: ' + ', '.join(required))

    if not isinstance(interfaces, list) or len(interfaces) > 100:
        fail('인터페이스 목록은 최대 100개입니다.')
    by_name = {}
    for spec in interfaces:
        fields(spec, ('formatVersion', 'name', 'displayName', 'description', 'properties', 'links', 'implementations'), '인터페이스')
        if spec['formatVersion'] != 1 or not name(spec['name']) or not spec['name'][0].isupper():
            fail('인터페이스 이름 또는 형식 버전이 잘못되었습니다.')
        if spec['name'] in by_name or spec['name'] in objects:
            fail('중복 인터페이스/객체 이름: ' + spec['name'])
        by_name[spec['name']] = spec
        text(spec['description'], spec['name'])
        text(spec['displayName'], spec['name'])
        for key in ('properties', 'links', 'implementations'):
            if not isinstance(spec[key], dict) or len(spec[key]) > 100:
                fail(spec['name'] + ': 잘못된 ' + key)
        if 'id' not in spec['properties'] or not spec['implementations']:
            fail(spec['name'] + ': id 속성과 구현 객체가 필요합니다.')
    for spec in interfaces:
        prefix = spec['name']
        for prop, p in spec['properties'].items():
            fields(p, ('dataType', 'nullable', 'description'), prefix + '.' + prop)
            if not name(prop) or p['dataType'] not in TYPES or type(p['nullable']) is not bool:
                fail(prefix + ': 속성 타입/NULL 정책을 확인하세요.')
            text(p['description'], prefix + '.' + prop)
        if spec['properties']['id']['nullable']:
            fail(prefix + ': id는 NULL을 허용할 수 없습니다.')
        for link, contract in spec['links'].items():
            fields(contract, ('target', 'cardinality', 'required', 'description'), prefix + '.' + link)
            fields(contract['target'], ('kind', 'name'), prefix + '.' + link)
            target = contract['target']
            if not name(link) or contract['cardinality'] not in ('ONE', 'MANY') or type(contract['required']) is not bool:
                fail(prefix + ': 관계 이름/개수/필수 여부를 확인하세요.')
            if target['kind'] not in ('object', 'interface') or target['name'] not in (objects if target['kind'] == 'object' else by_name):
                fail(prefix + ': 미정의 관계 대상 ' + str(target))
            text(contract['description'], prefix + '.' + link)
        for obj_name, impl in spec['implementations'].items():
            where = prefix + ' / ' + obj_name
            if obj_name not in objects:
                fail(where + ': 미정의 객체')
            fields(impl, ('properties', 'links'), where)
            if not isinstance(impl['properties'], dict) or not isinstance(impl['links'], dict):
                fail(where + ': 속성과 관계 매핑이 필요합니다.')
            obj = objects[obj_name]
            if set(impl['properties']) != set(spec['properties']):
                fail(where + ': 속성 매핑 누락/초과 ' + ', '.join(sorted(set(impl['properties']) ^ set(spec['properties']))))
            for prop, actual in impl['properties'].items():
                p = spec['properties'][prop]
                if not isinstance(actual, str) or actual not in obj['properties']:
                    fail(where + '.' + prop + ': 미정의 속성')
                source = obj['properties'][actual]
                if source['dataType'] != p['dataType']:
                    fail(where + '.' + prop + ': 타입 불일치')
                if not p['nullable'] and (source.get('nullable', True) or source.get('mappingStatus') in ('unmapped', 'needsCorrection')):
                    fail(where + '.' + prop + ': NULL 불가 계약을 충족하지 못합니다.')
                if prop == 'id' and actual != obj['primaryKey']:
                    fail(where + ': id는 실제 객체 PK에 매핑해야 합니다.')
            if set(impl['links']) - set(spec['links']):
                fail(where + ': 계약에 없는 관계 매핑')
            for link, contract in spec['links'].items():
                mapping = impl['links'].get(link)
                if mapping is None:
                    if contract['required']:
                        fail(where + '.' + link + ': 필수 관계 매핑 없음')
                    continue
                fields(mapping, ('linkType', 'direction'), where + '.' + link)
                if not isinstance(mapping['linkType'], str) or mapping['linkType'] not in links:
                    fail(where + '.' + link + ': 미정의 링크')
                if mapping['direction'] not in ('forward', 'reverse'):
                    fail(where + '.' + link + ': 잘못된 방향')
                resource = links[mapping['linkType']]
                definition = resource['definition']
                forward = mapping['direction'] == 'forward'
                start, end = (resource['source'], definition['target']) if forward else (definition['target'], resource['source'])
                if start != obj_name:
                    fail(where + '.' + link + ': 관계 방향의 출발 객체 불일치')
                target = contract['target']
                allowed = [target['name']] if target['kind'] == 'object' else by_name[target['name']]['implementations']
                if end not in allowed:
                    fail(where + '.' + link + ': 관계 대상 불일치')
                card = definition['cardinality'].split(':')
                if contract['cardinality'] == 'ONE' and card[1 if forward else 0] != '1':
                    fail(where + '.' + link + ': 관계 개수 ONE을 충족하지 못합니다.')
