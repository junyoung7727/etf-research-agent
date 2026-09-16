import * as api from './api-client'
import { SYMBOLS, candleView, money, percent, quoteView } from './market-view'

let currentCatalog=null
const instrument=k=>currentCatalog?.instruments.find(i=>i.id===SYMBOLS[k])
const errorText=e=>e instanceof Error ? e.message : '데이터 연결을 확인해 주세요.'
const dateLabel=value=>typeof value==='string' ? value.replace('T',' ').slice(0,16) : '기준 시각 없음'

// LiveTicker originally invents a new price every three seconds. Connected quotes
// must keep the provider's value, including zero returns and missing prices.
export function connectedTicker(Original) {
  return class extends Original {
    componentDidMount() {}
    renderVals() {
      const values=super.renderVals()
      if(values.isQuote||values.isRowQuote||values.isChgOnly) Object.assign(values,quoteView(instrument(this.props.seed)?.quote))
      if(values.isClock) values.clock=currentCatalog?.asOf?.slice(11,19)||'—'
      if(values.isIndex && currentCatalog?.dataMode==='REAL') Object.assign(values,{idxVal:'—',idxChg:'자료 없음',idxC:'#6B7684'})
      return values
    }
  }
}

export function connectedLogic(Original) {
  return class extends Original {
    _details={}
    _pending=new Set()
    _detailErrors={}
    _apiActive=false
    _mode='LOADING'
    _jobController=new AbortController()
    componentDidMount() {
      super.componentDidMount()
      this._apiActive=true
      this.refreshCatalog()
      this._unsubscribe=api.subscribe(data=>this.acceptCatalog(data),()=>this.setState({apiError:currentCatalog?'시세 연결이 끊겼어요. 마지막 값을 표시하고 있어요.':'시세 연결을 확인하지 못했어요.'}))
    }
    componentWillUnmount() {
      this._apiActive=false;this._unsubscribe?.();this._jobController.abort()
      super.componentWillUnmount()
    }
    async refreshCatalog() {
      try {this.acceptCatalog(await api.catalog())}
      catch(e){if(this._apiActive)this.setState({apiError:errorText(e)})}
    }
    acceptCatalog(data) {
      if(!this._apiActive)return
      if(this._mode==='REAL' && data.dataMode!=='REAL') {this.setState({apiError:'실데이터 연결 상태가 바뀌었어요. 예시 가격으로 바꾸지 않았어요.'});return}
      currentCatalog=data;this._mode=data.dataMode
      for(const [k,etf] of Object.entries(this.ETFS)) {
        const i=instrument(k)
        if(i) Object.assign(etf,{price:money(i.quote.price),dayChange:percent(i.quote.changeRatio),name:i.name})
        else if(this._mode==='REAL') Object.assign(etf,{price:'—',dayChange:'—'})
      }
      this._art={}
      this.setState({apiError:'',apiCatalogAt:data.asOf,apiFeedState:data.feedState})
      this.ensureDetail(this.state.stockEtf)
    }
    setState(update,callback) {
      super.setState(update,callback)
      if(this._apiActive && this.state.screen==='stock') this.ensureDetail(this.state.stockEtf)
    }
    async ensureDetail(k,force=false) {
      if(!SYMBOLS[k] || this._pending.has(k) || (!force && (this._details[k] || this._detailErrors[k])))return
      this._pending.add(k)
      try {
        const value=await api.detail(SYMBOLS[k])
        if(!this._apiActive)return
        if(this._mode==='REAL' && value.dataMode!=='REAL')throw new Error('상세 자료의 모드가 시세와 달라요.')
        this._details[k]=value;delete this._detailErrors[k];this._art={}
        this.setState({apiDetailLoaded:k})
        return true
      } catch(e) {if(this._apiActive){this._detailErrors[k]=errorText(e);this.setState({apiDetailLoaded:k})}return false}
      finally {this._pending.delete(k)}
    }
    liveQuote(k) {return quoteView(instrument(k)?.quote)}
    chart(range,k) {
      const count={ '1D':1,'1W':5,'1M':22,'6M':126,'1Y':250,'5Y':1250,'MAX':Infinity }[range]||25
      const all=this._details[k]?.candles||[],rows=all.slice(-count),view=candleView(all,count)
      const first=rows[0],last=rows.at(-1),r=first&&last?Number(last.close)/Number(first.open)-1:null
      return {...view,change:percent(r===null?null:String(r)),changeColor:r===null?'#6B7684':r<0?'#3182F6':'#F04452',changeBg:'#F2F4F6'}
    }
    artData(k) {
      const original=super.artData(k),detail=this._details?.[k]
      const chart=candleView(detail?.candles||[])
      return {...original,...chart,price:money(instrument(k)?.quote.price),chg:percent(instrument(k)?.quote.changeRatio),chgC:quoteView(instrument(k)?.quote).chgC}
    }
    async runAnalysis() {
      const k=this.state.stockEtf
      if(!SYMBOLS[k] || this.state.apiAnalysisBusy)return
      this.setState({apiAnalysisBusy:true,apiAnalysisError:''})
      try {
        if(this._mode==='REAL') {
          const job=await api.request('/api/analysis-jobs',{instrumentId:SYMBOLS[k]})
          await api.waitForJob(job,()=>{},this._jobController.signal)
        }
        const loaded=await this.ensureDetail(k,true)
        if(loaded===false)throw new Error(this._detailErrors[k])
        this.setState({apiReportOpen:true,apiReportIndex:0})
      } catch(e){this.setState({apiAnalysisError:errorText(e)})}
      finally{this.setState({apiAnalysisBusy:false})}
    }
    async agentAsk(question) {
      const text=String(question).trim().slice(0,1000)
      if(!text||this.state.agentBusy)return
      const k=SYMBOLS[this.state.stockEtf]?this.state.stockEtf:(this.state.watch||[]).find(k=>SYMBOLS[k])||'AXAI'
      const previous=this.state.agentMsgs||[]
      this.setState({agentBusy:true,agentDraft:'',agentMsgs:[...previous,{role:'user',text}]})
      try {
        const job=await api.request('/api/chat-jobs',{instrumentId:SYMBOLS[k],message:text,history:previous.slice(-4).map(m=>({role:m.role,text:m.text.slice(0,600)}))})
        const done=await api.waitForJob(job,()=>{},this._jobController.signal)
        if(!done.response || typeof done.response.text!=='string')throw new Error('답변 형식이 올바르지 않아요.')
        this.setState({agentMsgs:[...this.state.agentMsgs,{role:'assistant',text:done.response.text}],apiChatSources:done.response.sources||[]})
      }catch(e){this.setState({agentMsgs:[...this.state.agentMsgs,{role:'assistant',text:errorText(e)}]})}
      finally{this.setState({agentBusy:false},()=>this.agentScrollEnd())}
    }
    renderVals() {
      const values=super.renderVals(),s=this.state,k=s.stockEtf,detail=this._details?.[k]
      const reports=detail?.analyses||[],report=reports[s.apiReportIndex||0]||reports[0]
      const real=this._mode==='REAL',q=instrument(k)?.quote
      const label=real?'실시세 연결 · 전망·뉴스·커뮤니티는 예시':this._mode==='DEMO'?'데모 · 예시 시세·분석·커뮤니티':'데이터 연결 확인 중'
      const out={...values,apiLabel:label,apiError:s.apiError||'',apiHasError:!!s.apiError,
        apiRetry:()=>{this.refreshCatalog();this.ensureDetail(k,true)},
        apiDetailNote:this._detailErrors[k]||(detail?(q?.status==='STALE'?'지연된 시세 · ':'')+dateLabel(q?.asOf)+' 기준':SYMBOLS[k]?'자료를 불러오고 있어요.':'이 종목은 화면 체험용 예시입니다.'),
        apiDetailFailed:!!this._detailErrors[k],apiDetailRetry:()=>this.ensureDetail(k,true),
        apiReportOpen:!!s.apiReportOpen,apiOpenReport:()=>{this.setState({apiReportOpen:true});this.ensureDetail(k)},apiCloseReport:()=>this.setState({apiReportOpen:false}),
        agentBubbleOn:values.agentBubbleOn&&!s.apiReportOpen&&!values.isOnboarding,
        agentSub:real?'확인한 출처로 답해요':'예시 답변 · 외부 AI 호출 없음',
        onAgentDraft:e=>this.setState({agentDraft:e.target.value.slice(0,1000)}),
        apiReportTitle:report?.headline||'아직 분석 자료가 없어요',apiReportSummary:report?.summary||'새 분석을 요청하거나 연결 상태를 확인해 주세요.',apiReportDate:report?dateLabel(report.asOf)+' · '+report.modelId:'',
        apiReportFactors:(report?.factors||[]).map(f=>({...f,ready:f.status==='READY',metrics:f.metrics.map(m=>({...m,display:m.value===null?'자료 없음':m.value+' '+m.unit}))})),
        apiReportSources:(report?.sources||[]).map(source=>({...source,linked:typeof source.url==='string'&&/^https:\/\//.test(source.url)})),
        apiChatSources:(s.apiChatSources||[]).map(source=>({...source,linked:typeof source.url==='string'&&/^https:\/\//.test(source.url)})),
        apiReportDates:reports.map((r,index)=>({index,label:r.asOf.slice(5,10),bg:index===(s.apiReportIndex||0)?'#3D34E0':'#F2F4F6',c:index===(s.apiReportIndex||0)?'#FFFFFF':'#4E5968'})),
        apiSelectReport:e=>this.setState({apiReportIndex:Number(e.currentTarget.dataset.ari)}),
        apiRunAnalysis:()=>this.runAnalysis(),apiAnalysisDisabled:!!s.apiAnalysisBusy||(real&&!currentCatalog?.analysisEnabled),
        apiAnalysisLabel:s.apiAnalysisBusy?'분석하고 있어요':real?'새 분석 요청':'예시 분석 다시 보기',apiAnalysisError:s.apiAnalysisError||'',
      }
      if(real) Object.assign(out,{
        sumVerdict:'판단 보류',daNowLabel:'판단 보류',daNowC:'#8E8E93',daChanged:false,daSynth:report?.summary||'아직 확인된 분석 자료가 없어요.',
        daQuestion:report?.headline||'확인된 자료를 기다리고 있어요',artDateline:report?dateLabel(report.asOf):'분석 자료 없음',
        openDaSheet:out.apiOpenReport,openStoryFromStock:out.apiOpenReport,
        stFee:detail?.fundamentals.find(f=>f.label==='총보수 (연)')?.value||'자료 없음',stDist:detail?.fundamentals.find(f=>f.label==='분배율 (연)')?.value||'자료 없음',stTe:'자료 없음',
        compositionInsight:detail?.holdings.length?'확인된 편입 비중과 기준일을 표시해요.':'편입 원자료가 없어 구성과 투자 온도를 표시하지 않아요.',compositionInsightColor:'#6B7684',
        stHoldList:(detail?.holdings||[]).map(h=>({name:h.name,wL:(h.weight*100).toFixed(2)+'%',tag:'',c:'#6B7684',tc:'#6B7684',bg:'#F2F4F6'})),
        stThemeList:[],stThemeRows:[],stHoldToggleVisible:false,stThemeToggleVisible:false,
      })
      return out
    }
  }
}
