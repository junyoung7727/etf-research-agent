"""Publish reviewed view display properties to the configured ontology library."""
import hashlib
import copy
import json
import re
import sys
from pathlib import Path
import yaml

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import APP,EDGE_ONTOLOGY,METADATA
from ontology.oms.loader import read_definitions
from backend.design_models import source_catalog,validate_view_property


def updated_definition(raw,kind,addition,schema):
    doc=yaml.safe_load(raw)
    unchanged = (all(doc['properties'].get(p)==v for p,v in addition['properties'].items()) and
            all(doc['sourceMapping']['properties'].get(p)==v for p,v in addition['mappings'].items()) and
            doc['titleProperty']==addition['titleProperty'])
    original=copy.deepcopy(doc)
    for p,d in addition['properties'].items():
        if p in original['properties']:
            if original['sourceMapping']['properties'][p].get('kind')!='view_column':
                raise ValueError('Cannot overwrite a source property: '+kind+'.'+p)
            del original['properties'][p];del original['sourceMapping']['properties'][p]
            raw=re.sub(r'(?ms)^  '+re.escape(p)+r':\n.*?(?=^  \S|^\S|\Z)','',raw,count=1)
            raw=re.sub(r'(?ms)^    '+re.escape(p)+r':\n.*?(?=^    \S|^  \S|^\S|\Z)','',raw,count=1)
    if original['titleProperty'] not in (addition['previousTitleProperty'],addition['titleProperty']):
        raise ValueError('Title property changed since review: '+kind)
    original['titleProperty']=addition['previousTitleProperty']
    if hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=addition['baseSemanticHash']:
        raise ValueError('Object changed since review: '+kind)
    for p,d in addition['properties'].items():validate_view_property(addition['mappings'][p],d,schema)
    if unchanged:return None
    missing=addition['properties']
    prop_text=yaml.safe_dump({'properties':missing},sort_keys=False,allow_unicode=True).split('\n',1)[1]
    mapping_text='\n'.join(yaml.safe_dump({'sourceMapping':{'properties':{p:addition['mappings'][p] for p in missing}}},sort_keys=False,allow_unicode=True).splitlines()[2:])+'\n'
    raw=raw.replace('\nsourceMapping:', '\n'+prop_text+'sourceMapping:',1)
    raw=raw.replace('\nsourceConstraints:', '\n'+mapping_text+'sourceConstraints:',1)
    raw=raw.replace('titleProperty: '+doc['titleProperty']+'\n','titleProperty: '+addition['titleProperty']+'\n',1)
    result=yaml.safe_load(raw)
    assert set(result['properties'])==set(result['sourceMapping']['properties'])
    return raw


def publish():
    contract=json.loads((APP/'data/view-display-contracts.json').read_text(encoding='utf-8'))
    schema=source_catalog();writes=[]
    for kind,addition in contract['objects'].items():
        path=EDGE_ONTOLOGY/'metadata/object_types'/f'{kind}.yaml'
        raw=path.read_text(encoding='utf-8')
        revised=updated_definition(raw,kind,addition,schema)
        if revised is not None:writes.append((path,revised))
    docs=read_definitions(METADATA/'object_types',EDGE_ONTOLOGY/'metadata')
    plan_path=APP/'data/view-design.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
    hashes={key:hashlib.sha256(raw.encode()).hexdigest() for _,d,_ in docs if d['sourceMapping'].get('kind')!='curated'
            for key,raw in d['_definitionSources'].items() if not key.startswith('interface_types/')}
    allowed={'object_types/'+n+'.yaml' for n in contract['objects']}
    if any(plan['definitionHashes'].get(k)!=v for k,v in hashes.items() if k not in allowed):
        raise ValueError('Unrelated model change requires a separate design review')
    for path,raw in writes:
        path.write_text(raw,encoding='utf-8')
        hashes['object_types/'+path.name]=hashlib.sha256(raw.encode()).hexdigest()
    plan['definitionHashes']=hashes
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Published display contracts:',len(writes),'objects')


if __name__=='__main__':publish()
