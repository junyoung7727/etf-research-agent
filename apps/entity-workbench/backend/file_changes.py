"""Apply a small local file batch; restore originals if validation or writing fails."""
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def replace_file(path, content):
    path = Path(path)
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


@contextmanager
def file_changes(changes):
    original = {p: p.read_bytes() if p.exists() else None for p in changes}
    applied = []
    try:
        for path, content in changes.items():
            replace_file(path, content)
            applied.append(path)
        yield
    except BaseException:
        for path in reversed(applied):
            replace_file(path, original[path])
        raise
