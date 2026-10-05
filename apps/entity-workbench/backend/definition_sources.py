"""Union of library definitions and unpublished drafts; explicit file promotion."""
import hashlib
from pathlib import Path

from ontology.oms.loader import definition_files, read_definitions
from backend.file_changes import file_changes


def source_state(drafts, library):
    definition_files(drafts, library)  # Reject ambiguous definitions before showing a graph.
    digest = hashlib.sha256()
    locations = {}
    pending = []
    for label, root in (('library', library), ('draft', drafts)):
        for key, raw in sorted(definition_files(root).items()):
            digest.update((label + '/' + key + '\0' + raw).encode('utf8'))
            locations.setdefault(key, label)
            if label == 'draft':
                pending.append(key)
    return dict(sourceHash=digest.hexdigest(), pending=pending, locations=locations,
                libraryPath=str(Path(library).resolve()), draftPath=str(Path(drafts).resolve()))


def promote_definitions(drafts, library, source_hash, validate=None):
    drafts, library = Path(drafts), Path(library)
    if not library.is_dir():
        raise ValueError('Configured library metadata directory does not exist')
    state = source_state(drafts, library)
    if state['sourceHash'] != source_hash:
        raise ValueError('Definitions changed. Reload before applying.')
    read_definitions(drafts / 'object_types', library)
    if validate:
        validate()
    changes = {}
    for key in state['pending']:
        changes[library / key] = (drafts / key).read_bytes()
    # Library writes precede draft removal; failure restores both sides.
    for key in state['pending']:
        changes[drafts / key] = None
    with file_changes(changes):
        read_definitions(drafts / 'object_types', library)
        if validate:
            validate()
    return source_state(drafts, library)
