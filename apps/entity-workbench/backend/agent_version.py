"""Register agent releases and identify the exact runtime used by a benchmark."""
import hashlib
import json
from importlib.metadata import version as package_version,PackageNotFoundError
from pathlib import Path
import platform
import subprocess

MANIFEST='apps/entity-workbench/data/agent-version.json'
ROOT=Path(__file__).resolve().parents[3]


def protected(path):
    parts=Path(path).parts
    if path==MANIFEST or any(p in ('tests','docs','__pycache__') for p in parts):return False
    return path in ('CLAUDE.md','AGENTS.md','.github/workflows/agent-version.yml') or path.startswith(('apps/','tools/','.claude/'))


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()


def file_digest(root,paths):
    return digest({p:hashlib.sha256((root/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(paths)})


def source_digest(root):
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root).decode('utf8').split('\0')
    return file_digest(root,{p for p in paths if p and protected(p) and (root/p).is_file()})


def release(root=ROOT):
    value=json.loads((Path(root)/MANIFEST).read_text(encoding='utf8'))
    if type(value.get('version')) is not int or value['version']<1 or not str(value.get('summary','')).strip():
        raise ValueError('Invalid agent version manifest')
    history=value.get('history',[])
    if not isinstance(history,list) or any(not isinstance(r,dict) or type(r.get('version')) is not int for r in history):
        raise ValueError('Invalid agent version history')
    numbers=[r['version'] for r in history]+[value['version']]
    if numbers!=sorted(set(numbers)):raise ValueError('Agent version history must increase without reuse')
    return value


def check(root=ROOT,base=None):
    root=Path(root);value=release(root)
    if value.get('source_digest')!=source_digest(root):
        raise ValueError('Agent sources changed: update the agent version with version_agent.py bump --summary <change>')
    if base:
        subprocess.check_call(['git','rev-parse','--verify',base+'^{commit}'],cwd=root,stdout=subprocess.DEVNULL)
        old=subprocess.run(['git','show',base+':'+MANIFEST],cwd=root,capture_output=True,text=True,encoding='utf8')
        if old.returncode==0:
            previous=json.loads(old.stdout)
            if value['version']<previous['version'] or (value['source_digest']!=previous['source_digest'] and value['version']<=previous['version']):
                raise ValueError('Agent source changes require a version increase over the base revision')
            history=previous.get('history',[])
            if value['version']>previous['version']:history=history+[{k:v for k,v in previous.items() if k!='history'}]
            if value.get('history',[])[:len(history)]!=history:
                raise ValueError('Published agent version history must be preserved')
    return value


def bump(root=ROOT,summary=''):
    if not summary.strip():raise ValueError('Describe the agent change')
    root=Path(root);path=root/MANIFEST
    previous=release(root) if path.exists() else None
    history=previous.get('history',[])+[{k:v for k,v in previous.items() if k!='history'}] if previous else []
    value={'version':previous['version']+1 if previous else 1,'summary':summary.strip(),'source_digest':source_digest(root),'history':history}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return value


def snapshot(registered,runtime_source,catalog,model):
    runtime_source=Path(runtime_source)
    paths=[p.relative_to(runtime_source).as_posix() for p in runtime_source.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.yaml','.yml','.md','.toml')]
    if not paths:raise ValueError('Cannot identify the actual analysis harness sources')
    packages={}
    for name in ('claude-agent-sdk','anthropic'):
        try:packages[name]=package_version(name)
        except PackageNotFoundError:packages[name]='not_installed'
    value={'release':registered['version'],'summary':registered['summary'],'source_digest':registered['source_digest'],
           'runtime_digest':file_digest(runtime_source,paths),'catalog_digest':digest(catalog),'model':model,
           'runtime':{'python':platform.python_version(),'packages':packages}}
    identifier=digest(value)[:20]
    return {**value,'id':'agent-'+identifier,'label':f"v{registered['version']} · {identifier[:8]}"}
