const {el,request,json,answer,showEvidence}=CQ;
const $=s=>document.querySelector(s),runId=new URLSearchParams(location.search).get('run_id');
let detail,traceOffset=0,traceLoaded=false;
function showTab(name){
  if(!['summary','tools','trace'].includes(name))name='summary';
  for(const b of document.querySelectorAll('[data-tab]')){const active=b.dataset.tab===name;b.setAttribute('aria-selected',String(active));$('#'+b.dataset.tab).hidden=!active}
  history.replaceState(null,'',location.pathname+location.search+'#'+name);if(name==='trace'&&!traceLoaded&&detail)loadTrace();
}
async function artifact(name){try{const value=await request('/api/cq-benchmark/artifact?'+new URLSearchParams({run_id:runId,name}));if(!$('#evidence').open)$('#evidence').showModal();json($('#evidenceBody'),value.text)}catch(e){$('#runInfo').textContent=e.message}}
async function loadTrace(){
  traceLoaded=true;const target=$('#trace');let button=$('#moreTrace');if(button)button.remove();
  try{const page=await request('/api/cq-benchmark/trace?'+new URLSearchParams({run_id:runId,offset:traceOffset,limit:15}));
    if(!page.recorded)target.append(el('p','실행 원문이 저장되지 않았습니다.'));
    page.events.forEach((event,i)=>{const d=el('details',undefined,'trace-event');d.append(el('summary',`${traceOffset+i+1} · ${event.message_type||'이벤트'}`));const pre=el('pre');d.addEventListener('toggle',()=>{if(d.open&&!pre.hasChildNodes())json(pre,event)});d.append(pre);target.append(d)});
    traceOffset=page.next_offset;if(traceOffset!==null){button=el('button','다음 기록 불러오기');button.id='moreTrace';button.onclick=loadTrace;target.append(button)}
  }catch(e){traceLoaded=false;target.append(el('p',e.message,'review-notice'));button=el('button','다시 불러오기');button.id='moreTrace';button.onclick=loadTrace;target.append(button)}
}
async function load(){try{
  if(!runId)throw new Error('벤치마크에서 실행을 선택한 뒤 분석을 열어주세요.');
  detail=await request('/api/cq-benchmark/detail?'+new URLSearchParams({run_id:runId}));const run=detail.run;
  $('#backBenchmark').href=detail.benchmark_url;$('#title').textContent=run.case+' · 에이전트 분석';$('#runInfo').textContent=`${run.run_id} · ${run.model||'모델 미기록'} · ${run.execution_host||'환경 미기록'}`;
  const summary=$('#summary');summary.append(el('p',run.question,'question'));const body=el('div',undefined,'answer');answer(body,run.response?.answer);summary.append(body);
  if(run.response?.limitations?.length){const limits=el('details');limits.append(el('summary','분석이 명시한 한계'));const list=el('ul');for(const t of run.response.limitations)list.append(el('li',t));limits.append(list);summary.append(limits)}
  const claims=el('details');claims.append(el('summary','주장별 근거'));for(const c of run.response?.claims||[]){const item=el('div',undefined,'claim');item.append(el('p',c.claim),el('small',c.purpose,'muted'));for(const id of c.tool_run_ids||[]){const b=el('button','근거 '+id.slice(-8));b.onclick=()=>showEvidence(runId,id);item.append(b)}claims.append(item)}summary.append(claims);
  const tools=$('#tools');tools.append(el('h2',`저장된 도구 실행 ${detail.tools.length}회`),el('p','저장 완료 시각 순서입니다. 도구 응답은 모델에 반환된 원문 JSON으로 표시합니다.','muted'));
  detail.tools.forEach((call,i)=>{const item=el('div',undefined,'tool-row'),head=el('div',undefined,'check-heading');head.append(el('strong',`${i+1}. ${call.tool}`),el('span',call.error?'실패':'응답 저장','badge '+(call.error?'fail':'pass')));item.append(head,el('p',`${call.elapsed_ms??'—'} ms · ${call.finished_at||'시각 미기록'}`,'muted'));const params=el('pre');json(params,call.arguments);const b=el('button','입력·응답 JSON 보기');b.onclick=()=>showEvidence(runId,call.tool_run_id);item.append(params,b);tools.append(item)});
  const trace=$('#trace');trace.append(el('h2','SDK에 저장된 실행 원문'),el('p','기록된 메시지입니다. 관측되지 않은 추론을 재구성하지 않습니다.','muted'));const files=el('div',undefined,'artifact-links');for(const name of detail.artifacts){const b=el('button',name);b.onclick=()=>artifact(name);files.append(b)}trace.append(files);
  showTab(location.hash.slice(1)||'summary');
}catch(e){$('#runInfo').textContent=e.message}}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>showTab(b.dataset.tab);
$('#closeEvidence').onclick=()=>$('#evidence').close();window.addEventListener('hashchange',()=>showTab(location.hash.slice(1)));load();
