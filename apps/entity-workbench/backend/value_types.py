"""Read library definitions plus sparse drafts; explicitly apply reviewed file changes."""
import copy
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import yaml


from paths import EDGE_ONTOLOGY
from backend.catalog_delta import difference, apply_difference
from backend.file_changes import file_changes
RESOURCES = EDGE_ONTOLOGY


class RevisionConflict(ValueError):
    pass


class SourceConflict(ValueError):
    pass


def source_catalog(resources=RESOURCES, include_annotations=True):
    resources = Path(resources)
    if not (resources / 'metadata/value_types').is_dir() and (resources / 'resources/process/types').is_dir():
        resources = resources / 'resources'
    modern = (resources / 'metadata/value_types').is_dir()
    type_dir = resources / ('metadata/value_types/event_types' if modern else 'process/types')
    files = [('process/types/' + p.name, p) for p in sorted(type_dir.glob('*.yaml'))]
    if not files:
        raise ValueError('이벤트 종류 원본을 찾을 수 없습니다: ' + str(resources))
    files += [('process/news_thread_contract_v0_1.yaml', resources / (
        'rules/threading/news_thread_contract_v0_1.yaml' if modern else 'process/news_thread_contract_v0_1.yaml')),
        ('process/lifecycle_models_v0_1.yaml', resources / (
        'metadata/value_types/lifecycle_models_v0_1.yaml' if modern else 'process/lifecycle_models_v0_1.yaml'))]
    digest = hashlib.sha256()
    docs, sources = {}, []
    for name, path in files:
        raw = path.read_bytes()
        # Hash logical source names, so a package-only move does not invalidate drafts.
        digest.update(name.encode() + b'\0' + raw + b'\0')
        docs[name] = yaml.safe_load(raw)
        sources.append({'path': str(path), 'hash': hashlib.sha256(raw).hexdigest()})
    contract = docs['process/news_thread_contract_v0_1.yaml']
    lifecycle = docs['process/lifecycle_models_v0_1.yaml']['models']
    entries, families, predicates, roles, optional_fields, policies = [], set(), set(), set(), set(), set()
    for name, path in files[:-2]:
        for code, spec in docs[name]['types'].items():
            if any(e['code'] == code for e in entries):
                raise ValueError('중복 원본 이벤트 코드: ' + code)
            rule = contract.get('types', {}).get(code, {})
            identity = rule.get('identity', {})
            role_spec = spec.get('roles') or {}
            required = list(role_spec.get('identity') or [])
            optional = list(identity.get('optional_discriminators') or [])
            policy = rule.get('missing_identity_policy', 'EMIT_UNKNOWN_LINK_ONLY')
            family = spec.get('family') or ''
            families.add(family)
            predicates.update(spec.get('predicates') or [])
            for field in ('required', 'optional', 'identity', 'primary'):
                roles.update(role_spec.get(field) or [])
            optional_fields.update(optional)
            policies.add(policy)
            entries.append({'code': code, 'description': spec.get('note') or '', 'group': family,
                'rule': {'required': required, 'optional': optional, 'missingPolicy': policy},
                'origin': {'path': str(path), 'identityRequired': required,
                    'contractRequired': list(identity.get('required') or []),
                    'identityConflict': required != list(identity.get('required') or []),
                    'contractOptional': optional, 'missingPolicy': policy,
                    'roles': role_spec, 'predicates': spec.get('predicates') or [],
                    'lifecycleModel': spec.get('lifecycle_model'),
                    'executionNote': 'Reviewed local assemble_events._thread_key uses roles.identity; optional discriminators are not used. Production deployment is not verified.'}})
    def value_type(name, description, codes, used_by=()):
        return {'id': name, 'description': description, 'baseType': 'String',
                'usedBy': list(used_by), 'values': [
                    {'code': c, 'description': '', 'group': ''} for c in sorted(set(codes)) if c]}
    types = [value_type('EventTypeCode', 'Categories of source events and event threads.', [],
                        ['SourceEvent.eventType', 'EventThread.eventType'])]
    types[0]['values'] = sorted(entries, key=lambda e: e['code'])
    types += [value_type('EventFamilyCode', 'Top-level families in the event definition catalog.', families),
              value_type('EventPredicateCode', 'Actions declared by event definitions.', predicates,
                         ['SourceEvent.predicate']),
              value_type('EventRoleCode', 'Participant and field roles declared by event definitions.', roles),
              value_type('LifecycleModelCode', 'Named lifecycle definitions referenced by event categories.', lifecycle),
              value_type('EventStageCode', 'Stages and terminal states declared in lifecycle definitions.',
                         [s for m in lifecycle.values() for s in m.get('stages', []) + m.get('terminal', [])]),
              value_type('EventNoveltyStatus', 'How a source event updates an existing event thread.',
                         contract.get('tables', {}).get('event_thread_link', {}).get('fields', {}).get('novelty_status', [])),
              value_type('MissingIdentityPolicy', 'Handling when required event identity fields are missing.', policies)]
    catalog = {'valueTypes': types}
    annotations = resources / ('metadata/value_types/enum_annotations.yaml' if modern else 'process/enum_annotations.yaml')
    if include_annotations and annotations.exists():
        raw = annotations.read_bytes()
        digest.update(b'enum_annotations.yaml\0' + raw + b'\0')
        sources.append({'path': str(annotations), 'hash': hashlib.sha256(raw).hexdigest()})
        catalog = apply_difference(catalog, yaml.safe_load(raw))
    return {'catalog': catalog, 'sourceHash': digest.hexdigest(), 'sources': sources,
            'conditionFields': sorted(roles | optional_fields), 'lifecycleModels': lifecycle,
            'libraryPath': str(resources.resolve()), 'annotationsPath': str(annotations),
            'contractPath': str(files[-2][1])}


def read_catalog(path, resources=RESOURCES):
    baseline = source_catalog(resources)
    result = {**baseline, 'revision': 0, 'savedAt': None, 'sourceChanged': False, 'pendingCount': 0,
              'sourceCatalog': copy.deepcopy(baseline['catalog'])}
    if Path(path).exists():
        with closing(sqlite3.connect(path)) as db:
            row = db.execute('SELECT revision,payload,source_hash,saved_at FROM value_type_revision ORDER BY revision DESC LIMIT 1').fetchone()
        if row:
            payload = json.loads(row[1])
            delta = payload if payload.get('formatVersion') == 2 else difference(payload, baseline['catalog'])
            pending = sum(len(t.get('values', [])) + bool(set(t) - {'id', 'values'}) for t in delta['valueTypes'])
            result.update(revision=row[0], catalog=apply_difference(baseline['catalog'], delta),
                          sourceHash=row[2] if pending else baseline['sourceHash'], savedAt=row[3],
                          sourceChanged=bool(pending and row[2] != baseline['sourceHash']), pendingCount=pending,
                          pendingChanges=delta)
    result['currentSourceHash'] = baseline['sourceHash']
    return result


def validate_catalog(catalog, baseline):
    def string(value, limit=4000):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('텍스트 형식 또는 길이를 확인하세요.')
    if not isinstance(catalog, dict) or set(catalog) != {'valueTypes'}:
        raise ValueError('Value Type 목록이 필요합니다.')
    types = catalog['valueTypes']
    if not isinstance(types, list) or not 1 <= len(types) <= 100:
        raise ValueError('Value Type은 1–100개여야 합니다.')
    ids, codes_by_type = set(), {}
    for vt in types:
        if not isinstance(vt, dict):
            raise ValueError('Value Type 형식을 확인하세요.')
        name = vt.get('id')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,63}', name) or name in ids:
            raise ValueError('Value Type ID는 중복 없는 영문·숫자여야 합니다.')
        ids.add(name)
        if vt.get('baseType') != 'String':
            raise ValueError('현재 화면은 String enum을 관리합니다.')
        string(vt.get('description'))
        if not isinstance(vt.get('usedBy'), list) or any(not isinstance(x, str) for x in vt['usedBy']):
            raise ValueError('사용 속성 목록을 확인하세요.')
        values = vt.get('values')
        if not isinstance(values, list) or not 1 <= len(values) <= 2000:
            raise ValueError(name + ': 허용값은 1–2000개여야 합니다.')
        codes = set()
        for item in values:
            if not isinstance(item, dict):
                raise ValueError('허용값 형식을 확인하세요.')
            code = item.get('code')
            string(code, 180)
            if not code.strip() or code != code.strip() or code in codes:
                raise ValueError(name + ': 비어 있거나 중복된 코드입니다.')
            codes.add(code)
            string(item.get('description'))
            string(item.get('group', ''), 100)
            if name != 'EventTypeCode' and 'rule' in item:
                raise ValueError('스레드 규칙은 EventTypeCode의 값에만 연결합니다.')
        codes_by_type[name] = codes
    for original in baseline['catalog']['valueTypes']:
        if original['id'] not in codes_by_type or not {v['code'] for v in original['values']} <= codes_by_type[original['id']]:
            raise ValueError('원본 타입·코드는 삭제하거나 변경할 수 없습니다: ' + original['id'])
    fields = set(baseline['conditionFields']) | codes_by_type.get('EventRoleCode', set())
    policies = codes_by_type.get('MissingIdentityPolicy', set())
    for vt in types:
        if vt['id'] != 'EventTypeCode':
            continue
        for item in vt['values']:
            rule = item.get('rule')
            if not isinstance(rule, dict) or set(rule) != {'required', 'optional', 'missingPolicy'}:
                raise ValueError(item['code'] + ': 스레드 규칙을 확인하세요.')
            for key in ('required', 'optional'):
                values = rule[key]
                if not isinstance(values, list) or len(values) > 100 or any(not isinstance(x, str) for x in values):
                    raise ValueError('식별 조건 목록을 확인하세요.')
                if len(set(values)) != len(values) or not set(values) <= fields:
                    raise ValueError(item['code'] + ': 중복 또는 미정의 식별 조건입니다.')
            if not rule['required']:
                raise ValueError(item['code'] + ': 필수 식별 조건을 하나 이상 지정하세요.')
            if set(rule['required']) & set(rule['optional']):
                raise ValueError('같은 조건을 필수와 보조에 중복 지정할 수 없습니다.')
            if not isinstance(rule['missingPolicy'], str) or rule['missingPolicy'] not in policies:
                raise ValueError('정의되지 않은 결측 처리 정책입니다.')
    # Provenance is supplied by the reader, never trusted from a browser edit.
    originals = {t['id']: t for t in baseline['catalog']['valueTypes']}
    for vt in types:
        source = originals.get(vt['id'], {})
        vt['usedBy'] = source.get('usedBy', [])
        source_values = {v['code']: v for v in source.get('values', [])}
        for item in vt['values']:
            item.pop('origin', None)
            if 'origin' in source_values.get(item['code'], {}):
                item['origin'] = copy.deepcopy(source_values[item['code']]['origin'])


def save_catalog(path, catalog, revision, source_hash, resources=RESOURCES):
    baseline = source_catalog(resources)
    if source_hash != baseline['sourceHash']:
        raise SourceConflict('원본 정의가 변경되었습니다. 초안을 내보내고 원본과 비교하세요. 저장하지 않았습니다.')
    if type(revision) is not int or revision < 0:
        raise ValueError('올바른 저장 버전이 필요합니다.')
    catalog = copy.deepcopy(catalog)
    validate_catalog(catalog, baseline)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS value_type_revision (revision INTEGER PRIMARY KEY, payload TEXT NOT NULL, source_hash TEXT NOT NULL, saved_at TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        latest = db.execute('SELECT revision,source_hash FROM value_type_revision ORDER BY revision DESC LIMIT 1').fetchone()
        if (latest[0] if latest else 0) != revision:
            raise RevisionConflict('다른 탭에서 먼저 저장했습니다. 초안을 내보낸 뒤 최신 정의를 불러오세요.')
        current = read_catalog(path, resources)
        if current['sourceChanged']:
            raise SourceConflict('저장된 초안과 원본 버전이 다릅니다. 자동으로 덮어쓰지 않습니다.')
        db.execute('DELETE FROM value_type_revision')
        db.execute('INSERT INTO value_type_revision VALUES(?,?,?,?)',
                   (revision + 1, json.dumps(difference(catalog, baseline['catalog']), ensure_ascii=False), source_hash,
                    datetime.now(timezone.utc).isoformat()))
    return read_catalog(path, resources)


def promote_catalog(path, revision, source_hash, resources=RESOURCES):
    """Write native event/rule files and enum annotations; do not invoke Git or deploy."""
    state = read_catalog(path, resources)
    if revision != state['revision']:
        raise RevisionConflict('초안 버전이 변경되었습니다. 최신 확인 후 다시 반영하세요.')
    if state['sourceChanged'] or source_hash != state['currentSourceHash']:
        raise SourceConflict('라이브러리 원본이 변경되었습니다. 초안을 보존했습니다.')
    if not state['pendingCount']:
        return state
    desired = copy.deepcopy(state['catalog'])
    validate_catalog(desired, source_catalog(resources))
    delta = difference(desired, state['sourceCatalog'])
    native_events = {v['code']: v for v in state['sourceCatalog']['valueTypes'][0]['values']}
    documents = {}
    def document(file):
        file = Path(file)
        if file not in documents:
            documents[file] = yaml.safe_load(file.read_text(encoding='utf8'))
        return documents[file]
    for definition in delta['valueTypes']:
        if definition['id'] != 'EventTypeCode':
            continue
        for edit in definition.get('values', []):
            original = native_events.get(edit['code'])
            if not original or not original.get('origin'):
                raise ValueError('새 이벤트는 역할·속성 스키마를 먼저 정의해야 합니다: ' + edit['code'])
            spec = document(original['origin']['path'])['types'][edit['code']]
            if 'description' in edit:
                spec['note'] = edit['description']
            if 'group' in edit:
                spec['family'] = edit['group']
            if 'rule' in edit:
                rule = edit['rule']
                spec.setdefault('roles', {})['identity'] = rule['required']
                contract = document(state['contractPath']).setdefault('types', {}).setdefault(edit['code'], {})
                identity = contract.setdefault('identity', {})
                identity['required'] = rule['required']
                identity['optional_discriminators'] = rule['optional']
                contract['missing_identity_policy'] = rule['missingPolicy']
    changes = {p: yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).encode('utf8')
               for p, doc in documents.items()}
    with file_changes(changes):
        # Store only metadata absent from native definitions, never a second event catalog.
        native = source_catalog(resources, include_annotations=False)
        annotations = difference(desired, native['catalog'])
        annotation_path = Path(state['annotationsPath'])
        annotation_bytes = (yaml.safe_dump(annotations, allow_unicode=True, sort_keys=False).encode('utf8')
                            if annotations['valueTypes'] else None)
        with file_changes({annotation_path: annotation_bytes}):
            committed = source_catalog(resources)
            if difference(desired, committed['catalog'])['valueTypes']:
                raise ValueError('Library read-back differs from the reviewed definitions')
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                latest = db.execute('SELECT max(revision) FROM value_type_revision').fetchone()[0]
                if latest != revision:
                    raise RevisionConflict('반영 중 초안 버전이 변경되었습니다. 파일을 원복했습니다.')
                db.execute('DELETE FROM value_type_revision')
                db.execute('INSERT INTO value_type_revision VALUES(?,?,?,?)',
                    (revision + 1, json.dumps({'formatVersion': 2, 'valueTypes': []}),
                     committed['sourceHash'], datetime.now(timezone.utc).isoformat()))
    return read_catalog(path, resources)
