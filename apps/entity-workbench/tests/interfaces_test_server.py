"""Isolated editing server: never writes the user's library or drafts."""
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import server as workbench
from paths import EDGE_ONTOLOGY

root = Path(sys.argv[1])
library = root / 'library'
for kind in ('object_types', 'link_types', 'interface_types'):
    shutil.copytree(EDGE_ONTOLOGY / 'metadata' / kind, library / 'metadata' / kind)
workbench.DATA = root / 'data'
workbench.METADATA = root / 'drafts'
workbench.EDGE_ONTOLOGY = library
server = workbench.ThreadingHTTPServer(('127.0.0.1', 0), workbench.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(server.server_port, flush=True)
sys.stdin.readline()
server.shutdown()
server.server_close()
