import { test } from 'node:test'
import assert from 'node:assert/strict'
import worker from '../hosting/worker.js'

test('public HTML has a unique style nonce and no dynamic-script permission',async()=>{
  const env={ASSETS:{fetch:async()=>new Response('<html><head></head><body>EDGE</body></html>',{headers:{'Content-Type':'text/html','ETag':'old'}})}}
  const request=new Request('https://example.test/')
  const a=await worker.fetch(request,env),b=await worker.fetch(request,env)
  const csp=a.headers.get('content-security-policy')
  assert.match(csp,/script-src 'self';/)
  assert.ok(!csp.includes('unsafe-eval'))
  const nonce=(await a.text()).match(/content="([^"]+)"/)[1]
  assert.ok(csp.includes(nonce));assert.ok(!b.headers.get('content-security-policy').includes(nonce))
  assert.equal(a.headers.get('etag'),null)
})
test('public demo cannot mutate data or claim provider connectivity',async()=>{
  const response=await worker.fetch(new Request('https://example.test/api/health'),{})
  assert.deepEqual(await response.json(),{ok:true,dataMode:'DEMO',providersConnected:false})
  assert.equal((await worker.fetch(new Request('https://example.test/api/chat-jobs',{method:'POST'}),{})).status,405)
})
