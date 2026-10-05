"""Read object definitions and resolve their explicitly referenced Link Types."""
import re
from pathlib import Path

import yaml


def read_definitions(directory, library=None, include_interfaces=True):
    directory = Path(directory)
    files = definition_paths(directory.parent, library)
    documents = []
    used = set()
    for key, path in sorted(files.items()):
        if not key.startswith('object_types/'):
            continue
        raw = path.read_text(encoding='utf8')
        doc = yaml.safe_load(raw)
        sources = {f'object_types/{path.name}': raw}
        if 'linkTypes' in doc:
            if doc.get('links'):
                raise ValueError('Use linkTypes references or inline links, not both')
            links = []
            for name in doc['linkTypes']:
                if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) or name in used:
                    raise ValueError('Invalid or duplicate Link Type reference')
                link_path = files['link_types/' + name + '.yaml']
                link_raw = link_path.read_text(encoding='utf8')
                link = yaml.safe_load(link_raw)
                if link['id'] != name or link['source'] != doc['name']:
                    raise ValueError('Link Type owner or ID mismatch: ' + name)
                links.append(link['definition'])
                sources[f'link_types/{name}.yaml'] = link_raw
                used.add(name)
            doc['links'] = links
        doc['_definitionSources'] = sources
        documents.append((path, doc, raw))
    if not documents:
        raise ValueError('No object definitions found')
    defined = {p.stem for key, p in files.items() if key.startswith('link_types/')}
    if defined != used:
        raise ValueError('Unreferenced Link Type definitions: ' + ', '.join(sorted(defined - used)))
    if include_interfaces:
        from ontology.oms.interfaces import validate_interfaces
        interface_files = {key: path for key, path in files.items() if key.startswith('interface_types/')}
        interfaces = [yaml.safe_load(path.read_text(encoding='utf8')) for path in interface_files.values()]
        links = resolved_links(documents)
        validate_interfaces(interfaces, {d['name']: d for _, d, _ in documents}, links)
        for _, doc, _ in documents:
            doc['implementedInterfaces'] = [i['name'] for i in interfaces if doc['name'] in i['implementations']]
            for key, path in interface_files.items():
                if path.stem in doc['implementedInterfaces']:
                    doc['_definitionSources'][key] = path.read_text(encoding='utf8')
    return documents


def resolved_links(documents):
    result = {}
    for _, doc, _ in documents:
        names = doc['linkTypes'] if 'linkTypes' in doc else [f"{doc['name']}_{link['name']}_{link['target']}" for link in doc['links']]
        result.update({name: {'source': doc['name'], 'definition': link} for name, link in zip(names, doc['links'])})
    return result


def definition_paths(metadata, library=None):
    result = {}
    identities = {}
    for root in ([Path(library)] if library else []) + [Path(metadata)]:
        for kind in ('object_types', 'link_types', 'interface_types'):
            for path in sorted((root / kind).glob('*.yaml')):
                key = f'{kind}/{path.name}'
                doc = yaml.safe_load(path.read_text(encoding='utf8'))
                identity = (kind, doc['id'] if kind == 'link_types' else doc['name'])
                if kind == 'interface_types' and path.stem != doc['name']:
                    raise ValueError('Interface filename must match its name')
                if identity in identities and identities[identity] != key:
                    raise ValueError('Duplicate definition ID: ' + str(identity))
                identities[identity] = key
                if key in result:
                    if result[key].read_bytes() != path.read_bytes():
                        raise ValueError('Library/draft conflict: ' + key)
                    continue
                result[key] = path
    return result


def definition_files(metadata, library=None):
    return {key: path.read_text(encoding='utf8')
            for key, path in definition_paths(metadata, library).items()}
