"""Copy only nonignored EDGE project files into a dedicated release checkout."""
from pathlib import Path
import shutil
import subprocess
import sys

source=Path(__file__).resolve().parent.parent
workspace=source.parent.parent
name=sys.argv[1] if len(sys.argv)>1 else ''
if name not in ('edge-ci','edge-publish'):raise SystemExit('Choose edge-ci or edge-publish')
destination=(workspace/'private'/name).resolve()
if destination.parent != (workspace/'private').resolve():raise SystemExit('Release directory escaped workspace')
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z','--','apps/edge'],cwd=workspace).decode().split('\0')
count=0
for item in files:
    if not item:continue
    relative=Path(item).relative_to('apps/edge')
    if relative.name.startswith('.env') and relative.name!='.env.example':raise SystemExit('Environment file in release source')
    target=destination/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source/relative,target)
    count+=1
print(f'Staged {count} project files in {destination}; ignored files and parent research excluded.')
