"""Prepare the reviewed event measurement definition and its lossless graph mapping."""
import hashlib
import json
import sys
from pathlib import Path
import yaml

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from paths import METADATA, EDGE_ONTOLOGY
from ontology.oms.loader import read_definitions
from backend.view_design import snake, read_catalog
from backend.design_models import source_catalog, column_constraints


def prepare():
    kind = 'EventMeasurement'
    link = 'EventMeasurement_ForEvent_SourceEvent'
    fields = [
        ('id','String',False,'Identity of one reported measurement: source event ID and measurement ordinal, encoded as a JSON string array.'),
        ('sourceEventId','String',False,'ID of the source-specific event account to which this measurement belongs.'),
        ('measurementOrdinal','Short',False,'Stored ordinal distinguishing measurements within the same source-event account.'),
        ('metricCode','String',False,'What is measured, such as CONTRACT_VALUE, CONTRACT_DURATION, or CAPEX_VALUE. Interpret it with unit and periodBasis.'),
        ('reportedText','String',True,'Original text from which the measurement was extracted, including any ranges or approximations.'),
        ('value','Decimal',True,'Stored numeric measurement in the accompanying unit, without currency conversion or rescaling. A missing value remains unknown.'),
        ('unit','String',True,'Stored unit code, such as KRW, USD, PCT, DAY, or YEARS. PCT denotes a percentage; no implicit conversion is applied.'),
        ('periodBasis','String',False,'TOTAL means a total amount; ANNUAL means an annual amount; UNKNOWN means the time basis was not resolved. This does not identify a fiscal period.'),
        ('valueSource','String',False,'Origin of the stored value: PARSED from text, DART from a disclosure, or UNRESOLVED when numeric interpretation failed.'),
        ('parseStatus','String',True,'Recorded interpretation of the reported text, such as ok, approx_or_range, unit_mismatch, or no_number. A missing status is not proof of accuracy.'),
        ('argumentGroup','Short',True,'Stored group ordinal relating this measurement to event arguments within the same source account. Missing groups do not establish which participant a value describes.'),
        ('receiptNumber','String',True,'DART receipt number carried by the measurement, when present.'),
        ('availableAt','Timestamp',False,'Availability time of the owning source-event account. The source does not retain a separate measurement availability history.'),
        ('displayTitle','String',False,'Measurement code, reported text and event date, displayed together without changing the stored identity.'),
    ]
    types={'String':'text','Short':'smallint','Decimal':'numeric','Timestamp':'timestamp with time zone'}
    raw={'sourceEventId':'source_event_id','measurementOrdinal':'measure_ord','metricCode':'role_code',
         'reportedText':'surface','value':'value','unit':'unit','periodBasis':'basis','valueSource':'value_source',
         'parseStatus':'parse_flag','argumentGroup':'group_ord','receiptNumber':'dart_rcept_no'}
    catalog=source_catalog()
    inputs={'id':[('event_measure','source_event_id'),('event_measure','measure_ord')],
            'availableAt':[('source_event','available_at')],
            'displayTitle':[('event_measure','role_code'),('event_measure','surface'),('source_event','event_date')]}
    properties={}
    mappings={}
    for prop, dtype, nullable, description in fields:
        properties[prop]={'label':prop,'description':description,'dataType':dtype,'nullable':nullable,
            'sourceDataType':types[dtype],'sourceConstraints':None,'mappingStatus':'ready',
            'apiName':prop,'displayName':prop,'status':'experimental'}
        mappings[prop]=({'alias':'base','table':'event_measure','column':raw[prop]} if prop in raw else
            {'kind':'view_column','schema':'ontology_view','table':'event_measurement','column':snake(prop),
             'sqlFile':'sql/views/event_measurement.sql','inputs':[
                 {'schema':'public','table':table,'column':col} for table,col in inputs[prop]]})
        if prop in raw:
            properties[prop]['sourceConstraints']=column_constraints(catalog,'event_measure',raw[prop])
            properties[prop]['sourceDataType']=next(c['type'] for c in catalog['schema']['event_measure'] if c['name']==raw[prop])
    document={'formatVersion':2,'name':kind,'label':'Event measurement','description':
        'One numeric statement extracted for a source-specific event account. Each measurement retains its original wording, unit and time basis; different measures or conflicting statements remain separate records.',
        'group':'News & events','primaryKey':'id','identity':{'columns':['source_event_id','measure_ord'],'encoding':'jsonStringArray'},
        'properties':properties,'sourceMapping':{'connection':'aws_work','schema':'public','baseTable':'event_measure',
        'joins':[],'filters':[],'properties':mappings},'sourceConstraints':{},'dataIssues':[
        'Measurement availability is inherited from its source event; historical extraction revisions are not retained.',
        'A measurement has no assertion-level foreign key. Do not combine roles from different evidence versions.'],
        'apiName':kind,'displayName':'Event measurement','pluralDisplayName':'Event measurements',
        'titleProperty':'displayTitle','status':'experimental','visibility':'normal','linkTypes':[link]}
    relation={'id':link,'source':kind,'definition':{'name':'ForEvent','label':'For event',
        'description':'The source-specific event account in which this measurement was reported.',
        'target':'SourceEvent','sourceProperty':'sourceEventId','targetProperty':'id','cardinality':'N:1',
        'status':'experimental','sourceMapping':{'kind':'propertyMatch'},'mappingStatus':'defined',
        'apiName':'forEvent','displayName':'For event','pluralDisplayName':'For event',
        'inverse':{'apiName':'measurements','displayName':'Measurements','description':
        'Numeric statements recorded for this source-event account, with original units, wording and interpretation status.',
        'pluralDisplayName':'Measurements'},'backing':{'type':'foreignKey','configurationStatus':'ready'}}}
    for key,value in [('object_types/'+kind+'.yaml',document),('link_types/'+link+'.yaml',relation)]:
        path=METADATA/key
        if (EDGE_ONTOLOGY/'metadata'/key).exists():
            raise ValueError('Already promoted: '+key)
        path.write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=False),encoding='utf8')
    path=APP/'data/view-design.json'
    plan=json.loads(path.read_text(encoding='utf8'))
    plan['objects'][kind]={'viewName':'ontology_view.event_measurement','grain':document['description'],'issues':[],
        'referenceColumns':[{'column':'value_decimal','type':'text','viewNullable':True,
        'description':'Lossless decimal transport for PuppyGraph.','valuePolicy':'explicit_transform'}],
        'graphValueEncodings':{'value':{'encoding':'decimal_text','column':'value_decimal'}}}
    plan['relations'][link]={'readiness':'proposal','rowPolicy':'preserve_source_records','grain':relation['definition']['description'],
        'issues':[],'edgeIdentity':['id'],'physicalMapping':{'kind':'object_fk','source':kind,
        'edgeIdColumns':['id'],'fromColumn':'id','toColumn':'source_event_id','filters':{},'properties':{},
        'endpointPolicy':'existing_typed_objects_only'}}
    docs=read_definitions(METADATA/'object_types',EDGE_ONTOLOGY/'metadata')
    plan['definitionHashes']={key:hashlib.sha256(raw.encode('utf8')).hexdigest() for _,doc,_ in docs
        if doc['sourceMapping'].get('kind')!='curated' for key,raw in doc['_definitionSources'].items()
        if not key.startswith('interface_types/')}
    plan['revision']+=1
    path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert not read_catalog()['modelChanged']


if __name__=='__main__':
    prepare()
