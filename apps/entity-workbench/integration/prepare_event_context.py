"""Preserve event argument groups and document evidence on existing graph links."""
import hashlib
import json
import sys
from pathlib import Path
import yaml

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from paths import EDGE_ONTOLOGY,METADATA
from ontology.oms.loader import read_definitions
from backend.file_changes import file_changes
from backend.view_design import read_catalog
from backend.design_models import column_constraints,source_catalog


def prepare():
    path=APP/'data/view-design.json'
    plan=json.loads(path.read_text(encoding='utf8'))
    changes={}
    catalog=source_catalog()
    groups=[(['Company_ParticipatesIn_SourceEvent','Organization_ParticipatesIn_SourceEvent'],
        'ActorParticipation',[
            ('argumentGroup','argument_group','event_argument','group_ord','Short','smallint',
             'Stored group ordinal of this participant within the source-event account. Match a measurement group only within that same event; an absent group is unresolved.')]),
        (['NewsArticle_DescribesEvent_SourceEvent','Disclosure_DescribesEvent_SourceEvent'],
         'DocumentEventEvidence',[
            ('assertionId','assertion_id','event_evidence','assertion_id','String','text',
             'Identifier of the particular extracted assertion connecting this document to this event account.'),
            ('evidenceType','evidence_type','event_evidence','evidence_type','String','text',
             'Kind of supporting material recorded for this link, such as TITLE or DISCLOSURE_FACT.'),
            ('evidenceText','evidence_text','event_evidence','evidence_text','String','text',
             'Stored supporting text for this event-to-document link. Its scope is the recorded excerpt, not necessarily the full document.')])]
    for links,physical,fields in groups:
        columns=plan['physicalSources'][physical]['columns']
        for prop,col,table,raw,dtype,sqltype,description in fields:
            if col not in {x['column'] for x in columns}:
                columns.append({'column':col,'type':sqltype,'description':description,'viewNullable':True,
                    'valuePolicy':'source_value','source':{'table':table,'column':raw}})
        for identifier in links:
            target=EDGE_ONTOLOGY/'metadata/link_types'/(identifier+'.yaml')
            document=yaml.safe_load(target.read_text(encoding='utf8'));definition=document['definition']
            for prop,col,table,raw,dtype,sqltype,description in fields:
                constraint=column_constraints(catalog,table,raw)
                definition.setdefault('linkProperties',{})[prop]={'label':prop,'description':description,
                    'sourceDataType':next(x['type'] for x in catalog['schema'][table] if x['name']==raw),
                    'nullable':constraint['nullable'],'sourceConstraints':constraint,'mappingStatus':'ready',
                    'apiName':prop,'displayName':prop,'status':'experimental','dataType':dtype}
                definition['sourceMapping'].setdefault('properties',{})[prop]={'table':table,'column':raw}
                plan['relations'][identifier]['physicalMapping']['properties'][prop]=col
            changes[target]=yaml.safe_dump(document,allow_unicode=True,sort_keys=False).encode('utf8')
    with file_changes(changes):
        docs=read_definitions(METADATA/'object_types',EDGE_ONTOLOGY/'metadata')
        plan['definitionHashes']={key:hashlib.sha256(raw.encode('utf8')).hexdigest() for _,doc,_ in docs
            if doc['sourceMapping'].get('kind')!='curated' for key,raw in doc['_definitionSources'].items()
            if not key.startswith('interface_types/')}
        plan['revision']+=1
        with file_changes({path:(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf8')}):
            assert not read_catalog()['modelChanged']


if __name__=='__main__':prepare()
