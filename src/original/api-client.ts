import { Capacitor, CapacitorHttp } from '@capacitor/core'
import type { Catalog, EtfDetail } from '../domain'
import { validateCatalog, validateDetail } from './market-view'

const native=Capacitor.isNativePlatform()
const base=(import.meta.env.VITE_EDGE_API_BASE || '').replace(/\/$/,'')
const offline=import.meta.env.VITE_EDGE_BUNDLED_DEMO === '1'
if(base && (!/^https:\/\//.test(base) || new URL(base).origin!==base)) throw new Error('API 서버는 HTTPS 출처로 설정해야 합니다.')
let fixtures:Promise<{catalog:Catalog;details:Record<string,EtfDetail>}>|undefined

export async function request<T>(path:string,body?:unknown):Promise<T> {
  if(!path.startsWith('/api/')) throw new Error('허용되지 않은 API 경로입니다.')
  if(offline) {
    fixtures ||= fetch('/demo-api.json').then(r=>{if(!r.ok)throw new Error('기본 데모 자료를 읽지 못했어요.');return r.json()})
    const data=await fixtures
    if(path==='/api/catalog') return data.catalog as T
    const symbol=path.match(/^\/api\/etfs\/([0-9A-Z]{6})$/)?.[1]
    if(symbol && data.details[symbol]) return data.details[symbol] as T
    if(path==='/api/chat-jobs' && body && typeof body==='object' && 'instrumentId' in body) {
      const detail=data.details[String(body.instrumentId)]
      if(!detail)throw new Error('등록된 국내 ETF가 아닙니다.')
      const report=detail.analyses[0]
      return {id:'demo-chat',state:'SUCCEEDED',response:{text:'예시 답변입니다. '+report.headline+'\n\n'+report.summary,sources:report.sources,dataMode:'DEMO',modelId:'demo-fixture-v1',asOf:report.asOf}} as T
    }
    throw new Error('실제 분석은 서버 API 설정 후 사용할 수 있어요.')
  }
  let status:number,data:any
  if(native && base) {
    const r=await CapacitorHttp.request({url:base+path,method:body?'POST':'GET',headers:{Accept:'application/json',...(body?{'Content-Type':'application/json',Origin:base}:{})},data:body,responseType:'json',connectTimeout:12000,readTimeout:15000,disableRedirects:true})
    status=r.status;data=r.data
  } else {
    const response=await fetch(base+path,{method:body?'POST':'GET',credentials:'include',signal:AbortSignal.timeout(15000),headers:{Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})
    status=response.status;data=await response.json().catch(()=>null)
  }
  if(status<200 || status>=300) throw new Error(typeof data?.detail==='string'?data.detail:data?.error?.message||`요청을 처리하지 못했어요 (${status}).`)
  return data as T
}
export const catalog=async()=>validateCatalog(await request<Catalog>('/api/catalog'))
export const detail=async(symbol:string)=>validateDetail(await request<EtfDetail>('/api/etfs/'+symbol),symbol)
export function subscribe(onData:(c:Catalog)=>void,onError:()=>void) {
  if(offline) return ()=>{}
  if(native) {
    const timer=setInterval(()=>catalog().then(onData).catch(onError),10000)
    return ()=>clearInterval(timer)
  }
  const stream=new EventSource(base+'/api/quotes/stream',{withCredentials:true})
  stream.onmessage=e=>{try{onData(validateCatalog(JSON.parse(e.data)))}catch{onError()}}
  stream.onerror=onError
  return ()=>stream.close()
}
export interface Job {id:string;state:'RUNNING'|'SUCCEEDED'|'FAILED';failureCode?:string;response?:{text:string;sources:{title:string;url:string|null}[];dataMode:string;asOf:string;modelId:string}}
export async function waitForJob(initial:Job,onState:(state:Job)=>void,signal:AbortSignal) {
  let job=initial
  const until=Date.now()+75000
  while(job.state==='RUNNING' && Date.now()<until) {
    await new Promise<void>((resolve,reject)=>{
      const abort=()=>{clearTimeout(timer);reject(new Error('요청이 취소됐어요.'))}
      const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},4000)
      if(signal.aborted)abort();else signal.addEventListener('abort',abort,{once:true})
    })
    job=await request<Job>('/api/analysis-jobs/'+encodeURIComponent(job.id));onState(job)
  }
  if(job.state!=='SUCCEEDED') throw new Error(job.state==='FAILED'?'분석을 완료하지 못했어요. 설정·예산·근거 자료를 확인한 뒤 다시 시도해 주세요.':'분석 대기 시간이 초과됐어요. 잠시 후 다시 확인해 주세요.')
  return job
}
