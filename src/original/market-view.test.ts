import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import type { Candle, EtfDetail } from '../domain.ts'
import { candleView, decimal, percent, quoteView, validateCatalog, validateDetail } from './market-view.ts'

const fixtures=JSON.parse(readFileSync(new URL('../../public/demo-api.json',import.meta.url).pathname.replace(/^\/([A-Z]:)/,'$1'),'utf8'))
const detail=():EtfDetail=>structuredClone(fixtures.details['396500'])

test('zero return stays zero, missing values never become neutral or invented prices',()=>{
  assert.equal(percent('0'),'0.00%')
  assert.equal(percent('-.03'),'—')
  assert.equal(percent('-0.03'),'-3.00%')
  for(const missing of [null,undefined,'','NaN','Infinity',12]) assert.equal(decimal(missing),null)
  assert.deepEqual(quoteView(),{price:'—',chg:'—',chgC:'#4E5968',anim:''})
})
test('each offline record passes the same contract as the API and reconciles all holdings',()=>{
  validateCatalog(fixtures.catalog)
  for(const [id,d] of Object.entries(fixtures.details)) validateDetail(d as EtfDetail,id)
  const bad=detail();bad.residualWeight=0
  assert.throws(()=>validateDetail(bad,'396500'),/비중/)
  assert.throws(()=>validateDetail(detail(),'449450'),/ETF/)
})
test('bad candle dates, order, prices, completion flags and unsafe source URLs fail closed',()=>{
  const mutations:((d:EtfDetail)=>void)[]=[
    d=>{d.candles[0].date='2026-02-30'},d=>{d.candles.reverse()},
    d=>{d.candles[0].high='1'},d=>{d.candles[0].close='NaN'},
    d=>{delete (d.candles[0] as Partial<Candle>).isComplete},
    d=>{d.analyses[0].sources[0].url='javascript:alert(1)'},
    d=>{d.analyses[0].dataMode='REAL'},
  ]
  for(const mutate of mutations){const d=detail();mutate(d);assert.throws(()=>validateDetail(d,'396500'))}
})
test('twenty completed closes form the MA; an intraday bar cannot change it',()=>{
  const rows:Array<Candle>=Array.from({length:21},(_,i)=>({date:`2026-08-${String(i+1).padStart(2,'0')}`,open:String(100+i),high:String(101+i),low:String(99+i),close:String(100+i),volume:1,isComplete:i<20}))
  rows[20].close='10000';rows[20].high='10001'
  assert.equal(candleView(rows).ma20L,'109.5')
  assert.equal(candleView(rows.slice(0,19)).ma20L,'—')
  assert.equal(candleView(rows,5).ma20L,'109.5')
  assert.equal(candleView([]).candles.length,0)
  const v=candleView(rows.slice(0,1))
  assert.ok(Number.isFinite(v.candles[0].ry))
  assert.ok(!v.chartPoints.includes('NaN'))
})
