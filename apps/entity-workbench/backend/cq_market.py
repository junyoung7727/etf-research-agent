"""Market observations and exact Decimal calculations over stored graph evidence."""
from decimal import Decimal
from backend.cq_tools import SELECTOR,STRING,LIMIT,RESULT_REF


class MarketTools:
    def __init__(self,tools):
        self.tools=tools;self.graph=tools.graph
        common={'targets':SELECTOR,'start_date':STRING,'end_date':STRING,'limit':LIMIT}
        tools.register('get_price_observations','Read daily prices for the complete selected securities and optional ETF NAV. Preserve raw price basis, missing OHLC, currency and exact observation dates.',
            {**common,'include_nav':{'type':'boolean'}},['targets','start_date','end_date'],self.prices)
        tools.register('get_flow_observations','Read daily finalized or intraday estimated investor flows for selected securities. Quantity and monetary fields remain separate. Intraday values have UNKNOWN cumulative-versus-interval semantics: do not label them cumulative or incremental, sum slots or compare their totals with daily finalized flows.',
            {**common,'frequency':{'enum':['daily','intraday']}},['targets','start_date','end_date','frequency'],self.flows)
        tools.register('calculate_returns','Calculate exact endpoint price or per-unit NAV changes from a saved complete price dataset. Use price_field nav for NAV changes; NAV change is not a market-price or total return. Missing dates, incompatible bases or missing values remain unavailable.',
            {'dataset_ref':RESULT_REF,'start_date':STRING,'end_date':STRING,'price_field':{'enum':['closePrice','adjustedClosePrice','nav']},
             'basis_policy':{'enum':['require_recorded_basis','observed_close_only'],'description':'observed_close_only calculates the arithmetic change in recorded exchange closes; it does not certify corporate-action-adjusted or total return.'}},
            ['dataset_ref','start_date','end_date','price_field'],self.returns)
        tools.register('summarize_price_breadth','Summarize positive, negative, flat and unavailable returns for the entire saved target set. Sum original weights without renormalization; not performance attribution.',
            {'dataset_ref':RESULT_REF},['dataset_ref'],self.breadth)
        tools.register('calculate_nav_premium','Compare one ETF closing price and NAV on the exact same date. Return a premium only when currency and per-unit comparability are established by the source contract.',
            {'dataset_ref':RESULT_REF,'trade_date':STRING},['dataset_ref','trade_date'],self.nav)

    def observations(self,targets,start_date,end_date,kind,foreign_key,limit=20):
        start=self.tools.check_date(start_date);end=self.tools.check_date(end_date)
        if start>end:raise ValueError('Invalid observation date range')
        selection=self.tools.select(targets)
        selected=[x for x in selection['items'] if x['status']=='resolved' and x['object_type'] in ('Equity','ETF')]
        ids=[x['object_id'] for x in selected]
        items=self.graph.nodes(kind,where='n.'+foreign_key+' IN $instruments AND n.tradeDate>=date($start) AND n.tradeDate<=date($end)',
            parameters={'instruments':ids,'start':start_date,'end':end_date}) if ids else []
        return items,selection,{'start_date':start_date,'end_date':end_date,'object_type':kind,
            'outside_supported_scope':[x['object_id'] for x in selection['items'] if x not in selected]}

    def prices(self,targets,start_date,end_date,include_nav=False,limit=20):
        items,selection,scope=self.observations(targets,start_date,end_date,'DailyBar','instrumentId',limit)
        if include_nav:
            ids=[x['object_id'] for x in selection['items'] if x['status']=='resolved' and x['object_type']=='ETF']
            if ids:
                items+=self.graph.nodes('DailyNAV',where='n.etfInstrumentId IN $instruments AND n.tradeDate>=date($start) AND n.tradeDate<=date($end)',
                    parameters={'instruments':ids,'start':start_date,'end':end_date})
        return self.tools.result(items,selection=selection,scope={**scope,'dataset_kind':'price_observations',
            'ohlc_status':'Open/high/low source enrichment is deferred. Nulls are not replaced by close.',
            'nav_comparability':'DailyNAV.nav is per ETF unit in its ETF currency, as defined in the reviewed ontology. The currency is resolved from the ETF object.'},limit=limit)

    def flows(self,targets,start_date,end_date,frequency,limit=20):
        kind={'daily':'DailyInvestorFlow','intraday':'IntradayInvestorFlow'}[frequency]
        items,selection,scope=self.observations(targets,start_date,end_date,kind,'instrumentId',limit)
        currencies={r['object_id']:(r.get('object') or {}).get('properties',{}).get('currencyCode') for r in selection['items']}
        for item in items:
            if frequency=='intraday':
                item['aggregation_basis']='unknown: neither cumulative nor incremental is certified; do not sum slots'
            if currencies.get(item['properties'].get('instrumentId'))=='KRW':
                item['money_in_krw_100million']={k:str(Decimal(str(v))/Decimal('100000000'))
                    for k,v in item['properties'].items() if k.startswith('netVal') and v is not None}
        return self.tools.result(items,selection=selection,scope={**scope,'dataset_kind':'flow_observations',
            'frequency':frequency,'intraday_interval_semantics':'not_certified' if frequency=='intraday' else None},limit=limit)

    def returns(self,dataset_ref,start_date,end_date,price_field,basis_policy='require_recorded_basis'):
        if basis_policy=='observed_close_only' and price_field!='closePrice':raise ValueError('Observed-close policy cannot certify adjusted prices')
        dataset=self.tools.store.reference(dataset_ref,'dataset')
        if dataset['scope'].get('dataset_kind')!='price_observations':raise ValueError('A stored price dataset is required')
        if self.tools.check_date(start_date)>=self.tools.check_date(end_date):raise ValueError('Return start must precede end')
        prices={}
        for obj in dataset['items']:
            if obj['object_type']!=('DailyNAV' if price_field=='nav' else 'DailyBar'):continue
            prop=obj['properties'];identifier=prop['etfInstrumentId' if price_field=='nav' else 'instrumentId']
            prices.setdefault((identifier,prop['tradeDate']),[]).append(obj)
        rows=[]
        for member in dataset['selection']['items']:
            identifier=member['object_id'];left=prices.get((identifier,start_date),[]);right=prices.get((identifier,end_date),[])
            row={'object_id':identifier,'object_type':member['object_type'],'weight_ratio':member.get('weight_ratio'),
                 'start_date':start_date,'end_date':end_date,
                 'status':'unavailable','return_ratio':None,'input_ids':[o['object_id'] for o in left+right]}
            if len(left)!=1 or len(right)!=1:row['reason']='missing_or_ambiguous_exact_endpoint'
            else:
                a,b=left[0]['properties'],right[0]['properties']
                x,y=a.get(price_field),b.get(price_field)
                if price_field!='nav' and basis_policy=='require_recorded_basis' and (not a.get('priceBasis') or a.get('priceBasis')!=b.get('priceBasis')):
                    row['reason']='unknown_or_mismatched_price_basis'
                elif x is None or y is None or Decimal(x)<=0 or Decimal(y)<=0:
                    row['reason']='missing_or_nonpositive_price'
                elif not (member.get('object') or {}).get('properties',{}).get('currencyCode'):
                    row['reason']='unknown_currency'
                else:
                    row.update(status='calculated',return_ratio=str(Decimal(y)/Decimal(x)-1),
                        price_basis=a.get('priceBasis'),price_field=price_field,
                        currency=member['object']['properties']['currencyCode'],
                        interpretation='change in NAV per ETF unit in ETF currency; not market-price or total return' if price_field=='nav' else
                            'arithmetic change in observed closing quotes; adjustment comparability not certified' if basis_policy=='observed_close_only' else 'price return; not certified total return')
            rows.append(row)
        return self.tools.result(rows,selection=dataset['selection'],scope={'dataset_kind':'returns',
            'start_date':start_date,'end_date':end_date,'input_ref':dataset_ref,'formula':'end/start - 1','basis_policy':basis_policy,
            'value_kind':'nav_per_unit' if price_field=='nav' else 'market_price'},limit=100)

    def breadth(self,dataset_ref):
        dataset=self.tools.store.reference(dataset_ref,'dataset')
        if dataset['scope'].get('dataset_kind')!='returns':raise ValueError('A saved return dataset is required')
        if dataset['scope'].get('value_kind')=='nav_per_unit':raise ValueError('NAV changes cannot describe market-price breadth')
        groups={key:{'count':0,'raw_weight_sum':Decimal(0),'missing_weights':0} for key in ('up','down','flat','unavailable')}
        for row in dataset['items']:
            value=Decimal(row['return_ratio']) if row['status']=='calculated' else None
            group='unavailable' if value is None else 'up' if value>0 else 'down' if value<0 else 'flat'
            groups[group]['count']+=1
            if row.get('weight_ratio') is None:groups[group]['missing_weights']+=1
            else:groups[group]['raw_weight_sum']+=Decimal(str(row['weight_ratio']))
        rows=[{'direction':k,**v,'raw_weight_sum':str(v['raw_weight_sum'])} for k,v in groups.items()]
        return self.tools.result(rows,selection=dataset['selection'],scope={'dataset_kind':'breadth','input_ref':dataset_ref,
            'weights':'original raw weights, no normalization','price_basis_policy':dataset['scope'].get('basis_policy'),
            'interpretation':'directional breadth of selected price observations; not contribution to ETF return'})

    def nav(self,dataset_ref,trade_date):
        dataset=self.tools.store.reference(dataset_ref,'dataset')
        if dataset['scope'].get('dataset_kind')!='price_observations':raise ValueError('Price/NAV dataset required')
        self.tools.check_date(trade_date)
        rows=[]
        for member in dataset['selection']['items']:
            if member['object_type']!='ETF':continue
            prices=[x for x in dataset['items'] if x['object_type']=='DailyBar' and x['properties'].get('instrumentId')==member['object_id'] and x['properties'].get('tradeDate')==trade_date]
            navs=[x for x in dataset['items'] if x['object_type']=='DailyNAV' and x['properties'].get('etfInstrumentId')==member['object_id'] and x['properties'].get('tradeDate')==trade_date]
            row={'object_id':member['object_id'],'trade_date':trade_date,'status':'unavailable',
                'input_ids':[x['object_id'] for x in prices+navs],'premium_ratio':None}
            currency=(member.get('object') or {}).get('properties',{}).get('currencyCode')
            if len(prices)!=1 or len(navs)!=1:row['reason']='Exact date price/NAV missing or ambiguous'
            elif not currency:row['reason']='ETF currency is unknown'
            else:
                close=prices[0]['properties'].get('closePrice');nav=navs[0]['properties'].get('nav')
                if close is None or nav is None or Decimal(close)<=0 or Decimal(nav)<=0:
                    row['reason']='Price and NAV must be present and positive'
                else:row.update(status='calculated',premium_ratio=str(Decimal(close)/Decimal(nav)-1),currency=currency,
                    basis='Daily closing price versus daily NAV per ETF unit; not intraday premium')
            rows.append(row)
        return self.tools.result(rows,selection=dataset['selection'],scope={'input_ref':dataset_ref,'dataset_kind':'nav_premium',
            'formula':'close/nav - 1','unit_contract':'DailyNAV.nav and ETF.currencyCode'})
