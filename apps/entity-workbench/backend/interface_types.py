"""Interface contracts: validated local drafts and explicit library promotion."""
import copy
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import yaml

from paths import METADATA, EDGE_ONTOLOGY
from ontology.oms.loader import definition_paths, read_definitions, resolved_links
from ontology.oms.interfaces import validate_interfaces, TYPES
from backend.file_changes import file_changes
from backend.value_types import RevisionConflict, SourceConflict


def source_catalog(library=EDGE_ONTOLOGY / 'metadata', drafts=METADATA):
    paths = definition_paths(drafts, library)
    digest = hashlib.sha256()
    definitions = []
    for key, path in sorted(paths.items()):
        raw = path.read_bytes()
        digest.update(key.encode() + b'\0' + raw + b'\0')
        if key.startswith('interface_types/'):
            definitions.append(yaml.safe_load(raw))
    docs = read_definitions(Path(drafts) / 'object_types', library, include_interfaces=False)
    objects = {d['name']: d for _, d, _ in docs}
    links = resolved_links(docs)
    return {'catalog': {'interfaces': definitions}, 'sourceHash': digest.hexdigest(),
            'objects': objects, 'links': links, 'libraryPath': str(Path(library).resolve()), 'dataTypes': list(TYPES)}


def validate_catalog(catalog, baseline):
    if not isinstance(catalog, dict) or set(catalog) != {'interfaces'}:
        raise ValueError('인터페이스 목록이 필요합니다.')
    validate_interfaces(catalog['interfaces'], baseline['objects'], baseline['links'])


def read_catalog(path, library=EDGE_ONTOLOGY / 'metadata', drafts=METADATA):
    base = source_catalog(library, drafts)
    result = {**base, 'sourceCatalog': copy.deepcopy(base['catalog']), 'currentSourceHash': base['sourceHash'],
              'revision': 0, 'sourceChanged': False, 'pendingCount': 0}
    if Path(path).exists():
        with closing(sqlite3.connect(path)) as db:
            row = db.execute('SELECT revision,payload,source_hash FROM interface_revision ORDER BY revision DESC LIMIT 1').fetchone()
        if row:
            result['revision'] = row[0]
            if row[1] is not None:
                result.update(catalog=json.loads(row[1]), sourceHash=row[2], sourceChanged=row[2] != base['sourceHash'])
    old = {i['name']: i for i in base['catalog']['interfaces']}
    new = {i['name']: i for i in result['catalog']['interfaces']}
    result['pendingCount'] = sum(old.get(n) != new.get(n) for n in old.keys() | new.keys())
    try:
        validate_catalog(result['catalog'], base)
        result['validation'] = {'valid': True, 'error': None}
    except (ValueError, KeyError, TypeError) as exc:
        result['validation'] = {'valid': False, 'error': str(exc)}
    return result


def save_catalog(path, catalog, revision, source_hash, library=EDGE_ONTOLOGY / 'metadata', drafts=METADATA):
    if type(revision) is not int or revision < 0:
        raise ValueError('올바른 초안 버전이 필요합니다.')
    base = source_catalog(library, drafts)
    if source_hash != base['sourceHash']:
        raise SourceConflict('객체·관계 또는 인터페이스 원본이 변경되었습니다. 초안을 내보내고 비교하세요.')
    validate_catalog(catalog, base)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS interface_revision (revision INTEGER PRIMARY KEY, payload TEXT, source_hash TEXT NOT NULL, saved_at TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision,payload,source_hash FROM interface_revision ORDER BY revision DESC LIMIT 1').fetchone()
        if (row[0] if row else 0) != revision:
            raise RevisionConflict('다른 탭에서 먼저 저장했습니다. 편집 내용을 내보낸 뒤 최신 확인하세요.')
        if row and row[1] is not None and row[2] != base['sourceHash']:
            raise SourceConflict('저장된 초안의 원본이 변경되었습니다. 자동으로 덮어쓰지 않습니다.')
        payload = json.dumps(catalog, ensure_ascii=False) if catalog != base['catalog'] else None
        db.execute('DELETE FROM interface_revision')
        db.execute('INSERT INTO interface_revision VALUES(?,?,?,?)', (revision + 1, payload, source_hash, datetime.now(timezone.utc).isoformat()))
    return read_catalog(path, library, drafts)


def promote_catalog(path, revision, source_hash, library=EDGE_ONTOLOGY / 'metadata', drafts=METADATA):
    state = read_catalog(path, library, drafts)
    if type(revision) is not int or revision != state['revision']:
        raise RevisionConflict('초안 버전이 변경되었습니다.')
    if state['sourceChanged'] or source_hash != state['currentSourceHash']:
        raise SourceConflict('라이브러리 원본이 변경되었습니다. 초안은 보존했습니다.')
    validate_catalog(state['catalog'], state)
    if not state['pendingCount']:
        return state
    original = {i['name']: i for i in state['sourceCatalog']['interfaces']}
    desired = {i['name']: i for i in state['catalog']['interfaces']}
    changes = {}
    for name in original.keys() | desired.keys():
        if original.get(name) != desired.get(name):
            changes[Path(library) / 'interface_types' / (name + '.yaml')] = (
                yaml.safe_dump(desired[name], allow_unicode=True, sort_keys=False).encode('utf8') if name in desired else None)
            draft = Path(drafts) / 'interface_types' / (name + '.yaml')
            if draft.exists():
                changes[draft] = None
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT max(revision) FROM interface_revision').fetchone()[0] != revision:
            raise RevisionConflict('반영 중 초안 버전이 변경되었습니다.')
        if source_catalog(library, drafts)['sourceHash'] != source_hash:
            raise SourceConflict('반영 직전 원본이 변경되었습니다.')
        with file_changes(changes):
            committed = source_catalog(library, drafts)
            if {i['name']: i for i in committed['catalog']['interfaces']} != desired:
                raise ValueError('반영 후 정의가 저장한 초안과 다릅니다.')
            read_definitions(Path(drafts) / 'object_types', library)
            db.execute('DELETE FROM interface_revision')
            db.execute('INSERT INTO interface_revision VALUES(?,?,?,?)', (revision + 1, None, committed['sourceHash'], datetime.now(timezone.utc).isoformat()))
            db.commit()
    return read_catalog(path, library, drafts)
