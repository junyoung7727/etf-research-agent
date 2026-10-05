"""Audited v2 tool provider. All factual inputs come from the deployed graph."""
from datetime import date, datetime
from time import perf_counter
from jsonschema import Draft202012Validator
from backend.cq_graph import GraphFacts
from backend.cq_store import EvidenceStore


STRING={'type':'string','minLength':1}
REF={'type':'object','properties':{'object_type':STRING,'object_id':STRING},
     'required':['object_type','object_id'],'additionalProperties':False}
REFS={'type':'array','items':REF,'minItems':1,'maxItems':1000}
RESULT_REF={'type':'object','properties':{'tool_run_id':STRING,'path':{'enum':['/selection','/dataset']}},
            'required':['tool_run_id','path'],'additionalProperties':False}
SELECTOR={'oneOf':[
    {'type':'object','properties':{'kind':{'const':'objects'},'object_refs':REFS},'required':['kind','object_refs'],'additionalProperties':False},
    {'type':'object','properties':{'kind':{'const':'etf_holdings'},'etf_ref':REF,'holdings_date':STRING,
        'date_policy':{'enum':['exact','latest_on_or_before']}},'required':['kind','etf_ref','holdings_date','date_policy'],'additionalProperties':False},
    {'type':'object','properties':{'kind':{'const':'selection_ref'},'ref':RESULT_REF},'required':['kind','ref'],'additionalProperties':False}]}
LIMIT={'type':'integer','minimum':1,'maximum':100,'default':20}


class CQTools:
    def __init__(self,run,catalog,directory,cutoff):
        self.store=EvidenceStore(directory,cutoff)
        self.graph=GraphFacts(run,catalog,self.store.cutoff)
        self.schemas=[];self.handlers={}
        self.register('get_ontology_schema','Discover graph object types, properties and links; definitions are not observed facts.',
            {'object_types':{'type':'array','items':STRING}},[],self.schema)
        self.register('search_objects','Find named objects or observations using verified graph properties. Returns a stored complete dataset and a first page.',
            {'object_type':STRING,'query':{'type':'string','maxLength':120},'filters':{'type':'object'},'limit':LIMIT},['object_type'],self.search)
        self.register('get_objects','Resolve a batch of typed IDs. Keep missing IDs and distinct company/security identities.',
            {'object_refs':REFS},['object_refs'],self.get)
        self.register('get_linked_objects','Follow one declared graph link for a batch of objects; preserve source, direction and each role-bearing edge.',
            {'object_refs':REFS,'link_type':STRING,'direction':{'enum':['forward','reverse']},'limit':LIMIT},['object_refs','link_type'],self.linked)
        self.register('get_result_page','Read another page of a stored full dataset without rerunning the graph query or changing its cutoff.',
            {'dataset_ref':RESULT_REF,'offset':{'type':'integer','minimum':0},'limit':LIMIT},['dataset_ref','offset'],self.page)
        self.register('get_etf_holdings','Read all direct constituent holdings on an exact or explicitly selected earlier date. Preserve original weights and unresolved assets; no top-N or weight normalization.',
            {'etf_ref':REF,'holdings_date':STRING,'date_policy':{'enum':['exact','latest_on_or_before']},'limit':LIMIT},['etf_ref','holdings_date','date_policy'],self.holdings)

    def register(self,name,description,properties,required,handler):
        parameters={'type':'object','properties':properties,'required':required,'additionalProperties':False}
        self.schemas.append({'type':'function','function':{'name':name,'description':description,'parameters':parameters}})
        self.handlers[name]=(Draft202012Validator(parameters),handler)

    def call(self,name,arguments):
        started=perf_counter();begin=len(self.graph.queries)
        if name not in self.handlers:raise ValueError('Unknown tool: '+name)
        validator,handler=self.handlers[name]
        validator.validate(arguments)
        try:
            result,dataset=handler(**arguments)
            error=None
        except (ValueError,KeyError) as exc:
            error=str(exc);result={'status':'invalid_or_unavailable','reason':error};dataset=None
        # Connectivity and persistence failures propagate; they never become missing data.
        return self.store.commit(name,arguments,result,elapsed_ms=round((perf_counter()-started)*1000,2),
            queries=self.graph.queries[begin:],error=error,dataset=dataset)

    def result(self,items,*,selection=None,scope=None,limit=20):
        scope={'cutoff':self.store.cutoff,'source':'PuppyGraph',**(scope or {})}
        value={'items':items[:limit],'data_scope':scope,'total_rows':len(items),
               'page':{'complete':len(items)<=limit,'next_offset':limit if len(items)>limit else None}}
        if selection is not None:value['selection']=selection
        return value,{'items':items,'scope':scope,'selection':selection}

    def schema(self,object_types=None):
        selected=object_types or list(self.graph.objects)
        for kind in selected:self.graph.properties(kind)
        return {'objects':[self.graph.objects[k] for k in selected],
            'links':[r for r in self.graph.links.values() if r['source'] in selected or r['target'] in selected],
            'cutoff':self.store.cutoff,'fact_source':'PuppyGraph','supported_tools':list(self.handlers)},None

    def search(self,object_type,query='',filters=None,limit=20):
        return self.result(self.graph.nodes(object_type,query=query,filters=filters),limit=limit,
            scope={'object_type':object_type,'query':query,'filters':filters or {},'complete_within_query':True})

    def get(self,object_refs):
        selection=self.graph.get(object_refs)
        return self.result(selection['items'],selection=selection,limit=100)

    def linked(self,object_refs,link_type,direction='forward',limit=20):
        selection=self.graph.get(object_refs)
        return self.result(self.graph.linked(object_refs,link_type,direction),selection=selection,limit=limit,
            scope={'link_type':link_type,'direction':direction})

    def page(self,dataset_ref,offset,limit=20):
        return self.store.page(dataset_ref,offset,limit),None

    def check_date(self,value):
        parsed=date.fromisoformat(value)
        if parsed>datetime.fromisoformat(self.store.cutoff).date():raise ValueError('Requested date is after the analysis cutoff')
        return parsed

    def holdings(self,etf_ref,holdings_date,date_policy,limit=20):
        requested=self.check_date(holdings_date)
        if etf_ref['object_type']!='ETF':raise ValueError('ETF reference required')
        resolved=self.graph.get([etf_ref])
        if resolved['completeness']!='complete':raise ValueError('ETF not found')
        params={'etf':etf_ref['object_id'],'day':holdings_date,'cutoff':self.store.cutoff}
        selected=holdings_date
        if date_policy=='latest_on_or_before':
            rows=self.graph.query('MATCH (h:ETFHolding)-[:ETFHolding_ForETF_ETF]->(e:ETF) WHERE e.id=$etf AND h.tradeDate<=date($day) AND h.availableAt<=datetime($cutoff) RETURN max(h.tradeDate) AS day',params,objects=['ETF','ETFHolding'],links=['ETFHolding_ForETF_ETF'])
            selected=rows[0]['day'] if rows else None
        elif date_policy!='exact':raise ValueError('Unknown holdings date policy')
        items=self.graph.nodes('ETFHolding',filters={'etfInstrumentId':etf_ref['object_id']},
            where='n.tradeDate=date($day)',parameters={'day':selected}) if selected else []
        ids=list(dict.fromkeys(o['properties']['constituentInstrumentId'] for o in items))
        securities={}
        for kind in ('Equity','ETF'):
            for obj in self.graph.nodes(kind,ids=ids):securities.setdefault(obj['object_id'],[]).append(obj)
        members=[]
        for holding in items:
            prop=holding['properties'];found=securities.get(prop['constituentInstrumentId'],[])
            members.append({'object_type':found[0]['object_type'] if len(found)==1 else None,
                'object_id':prop['constituentInstrumentId'],'object':found[0] if len(found)==1 else None,
                'status':'resolved' if len(found)==1 else 'unresolved','holding_id':holding['object_id'],
                'weight_ratio':prop.get('weightRatio')})
        selection={'items':members,'requested_date':holdings_date,'selected_date':selected if items else None,
            'date_policy':date_policy,'staleness_days':(requested-date.fromisoformat(selected)).days if items else None,
            'completeness':'complete' if items and all(x['status']=='resolved' for x in members) else 'partial',
            'scope':'all available direct holding rows; no recursive expansion','etf_ref':etf_ref}
        return self.result(items,selection=selection,limit=limit,scope={'source_snapshot_completeness':'not_certified',
            'historical_revisions':'not_reconstructable','holdings_date':selected})

    def select(self,targets):
        if targets['kind']=='objects':return self.graph.get(targets['object_refs'])
        if targets['kind']=='selection_ref':return self.store.reference(targets['ref'],'selection')
        result,_=self.holdings(targets['etf_ref'],targets['holdings_date'],targets['date_policy'])
        return result['selection']

    def actors(self,selection):
        actors={};mapping=[];equities=[]
        for item in selection['items']:
            if item['status']!='resolved':continue
            ref={k:item[k] for k in ('object_type','object_id')}
            if ref['object_type'] in ('Company','Organization'):actors[(ref['object_type'],ref['object_id'])]=ref
            elif ref['object_type']=='Equity':equities.append(ref)
        for row in self.graph.linked(equities,'Company_Issues_Equity','reverse'):
            target=row['target'];ref={k:target[k] for k in ('object_type','object_id')}
            actors[(ref['object_type'],ref['object_id'])]=ref
            mapping.append({'security':row['source'],'actor':ref})
        return list(actors.values()),mapping
