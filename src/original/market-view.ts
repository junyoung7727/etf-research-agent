import type { Candle, Catalog, EtfDetail, Quote } from '../domain'

export const SYMBOLS:Record<string,string> = {AXAI:'396500',DEFN:'449450',GRID:'487230',KBND:'439870',MEDX:'364970',SOLR:'377990'}
export const decimal = (value:unknown):number|null => {
  if (typeof value !== 'string' || !/^-?\d+(\.\d+)?$/.test(value)) return null
  const number=Number(value)
  return Number.isFinite(number) ? number : null
}
export const money = (value:unknown) => {
  const n=decimal(value)
  return n === null ? '—' : '₩'+n.toLocaleString('ko-KR',{maximumFractionDigits:2})
}
export const percent = (value:unknown) => {
  const n=decimal(value)
  return n === null ? '—' : (n>0?'+':'')+(n*100).toFixed(2)+'%'
}
export function quoteView(q?:Quote) {
  const n=decimal(q?.changeRatio)
  return {price:money(q?.price),chg:percent(q?.changeRatio),chgC:n === null || n === 0 ? '#4E5968' : n>0 ? '#F04452' : '#3182F6',anim:''}
}
export function validateCatalog(value:Catalog):Catalog {
  if (!value || !['DEMO','REAL'].includes(value.dataMode) || !Array.isArray(value.instruments) || value.instruments.length>200) throw new Error('시세 응답 형식이 올바르지 않아요.')
  const seen=new Set()
  for(const i of value.instruments) {
    if (!i || !/^[0-9A-Z]{6}$/.test(i.id) || seen.has(i.id) || typeof i.name!=='string' || !i.quote || i.currency!=='KRW') throw new Error('국내 ETF 목록을 확인하지 못했어요.')
    for(const key of ['price','previousClose','changeRatio'] as const) if(i.quote[key] !== null && decimal(i.quote[key]) === null) throw new Error('시세 숫자를 확인하지 못했어요.')
    if (i.quote.price !== null && decimal(i.quote.price)! <= 0) throw new Error('유효하지 않은 가격이에요.')
    seen.add(i.id)
  }
  return value
}
export function validateDetail(value:EtfDetail,symbol:string):EtfDetail {
  validateCatalog({instruments:[value?.instrument],dataMode:value?.dataMode} as Catalog)
  if(value.instrument.id!==symbol || !Array.isArray(value.candles) || value.candles.length>5000 || !Array.isArray(value.holdings) || !Array.isArray(value.analyses) || !Array.isArray(value.fundamentals)) throw new Error('요청한 ETF의 자료가 아니에요.')
  let previous=''
  for(const c of value.candles) {
    const [o,h,l,close]=[c.open,c.high,c.low,c.close].map(decimal)
    if(!/^\d{4}-\d{2}-\d{2}$/.test(c.date) || !Number.isFinite(Date.parse(c.date)) || new Date(c.date).toISOString().slice(0,10)!==c.date || c.date<=previous || typeof c.isComplete!=='boolean' || !Number.isSafeInteger(c.volume) || c.volume<0 || [o,h,l,close].some(n=>n===null||n<=0) || l!>Math.min(o!,close!) || h!<Math.max(o!,close!)) throw new Error('일봉 자료의 순서나 가격 범위가 올바르지 않아요.')
    previous=c.date
  }
  const total=value.holdings.reduce((sum,h)=>sum+h.weight,0)+value.residualWeight
  if(value.holdings.some(h=>typeof h.name!=='string'||!Number.isFinite(h.weight)||h.weight<0||h.weight>1) || !Number.isFinite(value.residualWeight) || value.residualWeight<0 || Math.abs(total-1)>.000001) throw new Error('편입 비중의 합계를 확인하지 못했어요.')
  for(const report of value.analyses) {
    if(!report || report.dataMode!==value.dataMode || typeof report.headline!=='string' || typeof report.summary!=='string' || typeof report.asOf!=='string' || typeof report.modelId!=='string' || !Array.isArray(report.factors) || !Array.isArray(report.sources)) throw new Error('분석 응답 형식이 올바르지 않아요.')
    for(const f of report.factors) if(typeof f.label!=='string' || typeof f.explanation!=='string' || !Array.isArray(f.metrics) || f.metrics.some(m=>typeof m.label!=='string'||typeof m.unit!=='string'||(m.value!==null && decimal(m.value)===null))) throw new Error('분석 지표를 확인하지 못했어요.')
    for(const source of report.sources) if(typeof source.title!=='string' || typeof source.excerpt!=='string' || (source.url!==null && (typeof source.url!=='string'||!/^https:\/\//.test(source.url)))) throw new Error('분석 출처를 확인하지 못했어요.')
  }
  return value
}

// Match the original chart's 354×262 drawing area. Indicators use completed bars only.
export function candleView(all:Candle[],count=25) {
  const rows=all.slice(-count), empty={candles:[],ma5:'',ma20:'',grid:[],axis:[],ma5L:'—',ma20L:'—',chartPoints:'',areaPath:''}
  if(!rows.length) return empty
  const min=Math.min(...rows.map(c=>Number(c.low))),max=Math.max(...rows.map(c=>Number(c.high))),pad=Math.max((max-min)*.06,max*.001)
  const lo=min-pad,hi=max+pad
  const x=(i:number)=>16.5+i*321/Math.max(1,rows.length-1)
  const y=(p:number)=>+(42+(hi-p)/(hi-lo)*208).toFixed(2)
  const start=all.length-rows.length
  const average=(n:number,index:number) => {
    const window=all.slice(0,index+1).filter(c=>c.isComplete).slice(-n)
    return window.length===n ? window.reduce((sum,c)=>sum+Number(c.close),0)/n : null
  }
  const path=(n:number)=>rows.map((_,i)=>{const value=average(n,start+i);return value===null?'':`${i===0||average(n,start+i-1)===null?'M':'L'}${x(i)} ${y(value)}`}).join(' ')
  const points=rows.map((r,i)=>`${(i*362/Math.max(1,rows.length-1)).toFixed(1)},${(152-(Number(r.close)-lo)/(hi-lo)*128).toFixed(1)}`)
  const label=(n:number)=>{const value=average(n,all.length-1);return value===null?'—':value.toLocaleString('ko-KR',{maximumFractionDigits:2})}
  return {
    candles:rows.map((r,i)=>{const o=y(Number(r.open)),c=y(Number(r.close));return {x:x(i),rx:x(i)-3.5,wy1:y(Number(r.high)),wy2:y(Number(r.low)),ry:Math.min(o,c),rh:Math.max(1.2,Math.abs(o-c)),c:Number(r.close)>=Number(r.open)?'#F23645':'#2962FF'}}),
    ma5:path(5),ma20:path(20),ma5L:label(5),ma20L:label(20),
    grid:[.25,.5,.75].map(r=>{const p=lo+(hi-lo)*r;return {y:y(p),pct:(y(p)/262*100).toFixed(1)+'%',l:Math.round(p).toLocaleString('ko-KR')}}),
    axis:[...new Set([0,Math.floor((rows.length-1)/2),rows.length-1])].map(i=>({pct:(x(i)/354*100).toFixed(1)+'%',l:rows[i].date.slice(5).replace('-','.')})),
    chartPoints:points.join(' '),areaPath:'M0,170 L'+points.join(' L')+' L362,170 Z',
  }
}
