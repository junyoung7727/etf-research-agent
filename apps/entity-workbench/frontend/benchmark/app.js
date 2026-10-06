const {el,request,showEvidence,badge}=CQ;
const $=s=>document.querySelector(s);
let data,current,matrix,selection=0;
function link(text,url,cls){const a=el('a',text,cls);a.href=url;return a}
function caseId(run){return /^CQ\d{2}/.exec(run?.case||'')?.[0]}
function versionId(run){return run?.agent_version?.id||'unversioned'}
function versionRuns(){return data.runs.filter(r=>versionId(r)===matrix?.version)}
function renderCases(){
  $('#runs').replaceChildren();
  for(const c of data.cases){
    const runs=versionRuns().filter(r=>caseId(r)===c.id),latest=matrix?.rows.find(r=>r.case===c.id);
    const b=el('button',undefined,'run'+(caseId(current)===c.id?' selected':''));
    b.append(el('strong',c.id),el('span',c.title||c.question),el('small',runs.length+'회 실행'));b.title=c.question;
    b.onclick=()=>{const target=data.runs.find(r=>r.run_id===latest?.run_id)||runs[0];if(target)selectRun(target.run_id);else{selection++;current={case:c.id};renderCases();$('#detail').replaceChildren(el('h2',c.id),el('p',c.question),el('p','아직 저장된 실행이 없습니다.','muted'))}};
    $('#runs').append(b);
  }
}
function renderMatrix(){
  const select=$('#versionSelect');select.replaceChildren();
  for(const version of matrix.versions){const option=el('option',version.label+' · '+version.run_count+'회');option.value=version.id;option.selected=version.id===matrix.version;select.append(option)}
  const selected=matrix.versions.find(v=>v.id===matrix.version);
  $('#versionInfo').textContent=selected.summary+(selected.model?' · 모델 '+selected.model:'')+' '+matrix.selection_rule;
  const wrap=el('div',undefined,'matrix-scroll'),table=el('table',undefined,'matrix-table'),head=el('thead'),groups=el('tr'),labels=el('tr'),body=el('tbody');
  wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','전체 CQ 결과');
  const name=el('th','CQ'),common=el('th','공통 기준'),specific=el('th','CQ별 기준');name.rowSpan=2;name.scope='col';common.colSpan=3;common.scope='colgroup';specific.scope='colgroup';groups.append(name,common,specific);
  for(const title of ['기술 검사','종합 판정','분석']){const th=el('th',title);th.rowSpan=2;th.scope='col';groups.append(th)}
  for(const title of ['사실 정확성','결론 타당성','조사 완결성','요구 충족']){const th=el('th',title);th.scope='col';labels.append(th)}
  for(const row of matrix.rows){
    const tr=el('tr',undefined,current?.run_id===row.run_id&&row.run_id?'selected':''),title=el('th');title.scope='row';
    const name=el(row.run_id?'button':'strong',row.case+' · '+row.title,'matrix-cq');
    if(row.run_id)name.onclick=async()=>{await selectRun(row.run_id);$('#detail').scrollIntoView({block:'start'})};
    title.append(name,el('small',({answered:'답변 완료',error:'실행 오류',running:'실행 중',not_run:'미실행'})[row.execution_status]||row.execution_status));
    if(row.contract_version)title.append(el('small','평가 계약 v'+row.contract_version));tr.append(title);
    if(row.evaluator_release)title.append(el('small','평가기 v'+row.evaluator_release));
    for(const id of ['accuracy','reasoning','research','fulfillment']){
      const check=row.checks.find(c=>c.id===id),cell=el('td');
      if(row.run_id){const button=el('button',undefined,'matrix-verdict');button.append(badge(check?.status||'not_evaluated'));button.setAttribute('aria-label',row.case+' '+(check?.name||id)+' 상세');
        button.onclick=async()=>{await selectRun(row.run_id);const target=document.getElementById('check-'+id);if(target){target.open=true;target.focus();target.scrollIntoView({block:'center'})}};cell.append(button)
      }else cell.append(badge('not_run'));
      tr.append(cell);
    }
    for(const status of [row.technical_status,row.overall]){const cell=el('td');cell.append(badge(status));tr.append(cell)}
    const analysis=el('td');if(row.run_id)analysis.append(link('보기 ↗',row.analysis_url));else analysis.textContent='—';tr.append(analysis);body.append(tr);
  }
  head.append(groups,labels);table.append(head,body);wrap.append(table);$('#matrixTable').replaceChildren(wrap);
}
async function chooseVersion(version='',runId='',push=true){
  const ticket=++selection;
  try{
    const value=await request('/api/cq-benchmark/matrix?'+new URLSearchParams({version}));if(ticket!==selection)return;
    matrix=value;current=null;renderMatrix();renderCases();
    const target=runId&&versionRuns().some(r=>r.run_id===runId)?runId:matrix.rows.find(r=>r.run_id)?.run_id;
    if(target)await selectRun(target,push);
    else{$('#detail').replaceChildren(el('h2','이 버전의 CQ 실행이 없습니다.'),el('p','실행 후 평가하면 전체 표에 결과가 표시됩니다.'));if(push)history.pushState(null,'','/benchmark?'+new URLSearchParams({version:matrix.version}))}
  }catch(error){if(ticket===selection)$('#matrixTable').replaceChildren(el('p',error.message,'review-notice'))}
}
function checkCard(check,run){
  const card=el('details',undefined,'check '+check.status),head=el('summary',undefined,'check-heading');
  card.id='check-'+check.id;card.tabIndex=-1;card.open=['fail','unknown'].includes(check.status);
  head.append(el('strong',check.name),badge(check.status));card.append(head,el('p',check.reason,'check-reason'));
  if(check.answer_span)card.append(el('blockquote',check.answer_span));
  for(const id of check.evidence_ids||[]){const b=el('button','근거 '+id.slice(-8),'evidence-button');b.onclick=()=>showEvidence(run.run_id,id);card.append(b)}
  if(check.rule){const d=el('details');d.append(el('summary','판정 기준'),el('p',check.rule,'muted'));card.append(d)}
  return card;
}
function criteriaOverview(checks,run){
  const overview=el('div',undefined,'criteria-overview');overview.id='criteriaOverview';
  const wrap=el('div',undefined,'criteria-table-scroll'),table=el('table',undefined,'criteria-table');
  const head=el('thead'),groups=el('tr'),labels=el('tr'),body=el('tbody'),verdicts=el('tr');
  wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','분석 품질 평가표');
  const label=el('th','CQ'),common=el('th','공통 기준'),specific=el('th','CQ별 기준'),row=el('th',caseId(run));
  label.scope='col';label.rowSpan=2;common.scope='colgroup';common.colSpan=3;specific.scope='colgroup';row.scope='row';
  groups.append(label,common,specific);verdicts.append(row);
  for(const check of checks){
    const column=el('th',check.name),cell=el('td'),button=el('button',undefined,'verdict-link '+check.status);button.type='button';column.scope='col';
    button.append(badge(check.status));button.setAttribute('aria-controls','check-'+check.id);
    button.setAttribute('aria-label',check.name+' · '+button.textContent+' · 상세 보기');
    button.onclick=()=>{const target=document.getElementById('check-'+check.id);target.open=true;target.focus({preventScroll:true});target.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})};
    labels.append(column);cell.append(button);verdicts.append(cell);
  }
  head.append(groups,labels);body.append(verdicts);table.append(el('caption','분석 품질'),head,body);wrap.append(table);overview.append(wrap);
  return overview;
}
function renderDetail(detail){
  const run=detail.run,e=detail.evaluation,c=e.contract;current=run;renderCases();renderMatrix();
  const body=$('#detail');body.replaceChildren();
  const heading=el('div',undefined,'detail-heading'),title=el('div');
  title.append(el('p',(caseId(run)||run.case)+' / '+(run.agent_version?.label||'버전 미기록'),'eyebrow'),el('h2',c?.title||run.case));
  heading.append(title,link('에이전트 분석 보기 ↗',detail.analysis_url,'primary-link'));body.append(heading);
  const state=el('div',undefined,'run-state');state.append(badge(e.overall),el('span',e.review_status==='current'?'평가 에이전트 판정 · 전문가 교정 전':run.status==='answered'?'답변 생성 완료':run.status==='running'?'실행 중':'실행 오류','muted'));body.append(state);
  body.append(criteriaOverview(e.agent_checks,run));
  const technical=el('details',undefined,'technical-checks'),technicalHead=el('summary');technical.id='technicalChecks';
  const technicalStatus=e.code_checks.some(x=>x.status==='fail')?'fail':e.code_checks.length&&e.code_checks.every(x=>x.status==='pass')?'pass':'not_evaluated';
  technical.open=technicalStatus==='fail';technicalHead.append(el('strong','기술 검사 '),badge(technicalStatus));technical.append(technicalHead);
  for(const check of e.code_checks)technical.append(checkCard(check,run));body.append(technical);
  const select=el('select');select.id='runSelect';select.setAttribute('aria-label','같은 CQ의 실행 선택');
  for(const r of versionRuns().filter(r=>caseId(r)===caseId(run))){const o=el('option',r.run_id+' · '+(r.execution_host||r.status));o.value=r.run_id;o.selected=r.run_id===run.run_id;select.append(o)}
  select.onchange=()=>selectRun(select.value);body.append(select,el('p','기준시각 '+run.cutoff+' · 모델 '+(run.model||'미기록'),'muted'));
  const scenario=data.cases.find(x=>x.id===caseId(run))?.scenario_question;
  if(scenario&&scenario!==run.question){
    const notice=el('p','수정 전 질문으로 실행한 기록입니다. 아래 판정은 당시 입력에 대한 결과이며, 수정된 질문은 다시 실행해야 합니다.','review-notice');notice.id='scenarioNotice';
    const question=el('p',scenario,'question');question.id='currentQuestion';body.append(notice,el('h4','현재 CQ 질문'),question);
  }
  const q=el('details');q.append(el('summary','이 실행의 실제 입력 질문'),el('p',run.question,'question'));body.append(q);
  const note=el('div',undefined,'scope-note');note.append(el('strong','계산 재현 제외'),el('span','수치·단위·기간은 평가 에이전트가 문장과 근거를 대조합니다. 자동 수치 일치 검사로 표시하지 않습니다.'));body.append(note);
  if(e.review_status!=='current')body.append(el('p',({missing:'새 계약의 에이전트 평가가 아직 없습니다.',stale:'답변·근거·계약이 바뀌어 기존 평가를 적용하지 않았습니다.',invalid:'저장된 평가 형식이나 인용이 유효하지 않습니다.'})[e.review_status]||'미평가','review-notice'));
  if(e.reviewer)body.append(el('p','평가자 '+(e.reviewer.model||e.reviewer.method||'기록 확인')+(e.reviewer.agent_release?' · 평가기 v'+e.reviewer.agent_release:'')+' · 독립 의미 판정, 전문가 교정 전','muted'));
  if(e.overall==='review_needed'&&e.agent_proposal==='pass')body.append(el('p','평가 에이전트는 통과를 제안했습니다. 아직 정확도가 검증되지 않은 평가자이므로 최종 합격으로 집계하지 않습니다.','review-notice'));
  const quality=el('section',undefined,'evaluation-group');quality.id='qualityDetails';quality.append(el('h3','평가 상세'));
  for(const check of e.agent_checks)quality.append(checkCard(check,run));body.append(quality);
  renderEfficiency(body,e,run);
  if(c){
    const d=el('details',undefined,'contract');d.append(el('summary','CQ 평가 계약 · v'+c.version),el('h4','중대 오류'));
    const errors=el('ul');for(const t of c.critical_errors)errors.append(el('li',t));
    d.append(errors,el('h4','종료 요건'),el('p',c.completion_conditions),el('h4','참조 조사 흐름'));
    const steps=el('ol');for(const t of c.reference_path)steps.append(el('li',t));
    d.append(steps,el('p','대체 경로와 일괄 조회를 허용합니다. 이 흐름은 검증된 최소 호출 횟수가 아닙니다.','muted'));body.append(d);
  }
  if(run.review){const old=el('details',undefined,'legacy');old.append(el('summary','이전 방식의 검토 기록 · 새 평가에 합산하지 않음'));const list=el('ul');for(const t of run.review.findings||[])list.append(el('li',t));old.append(list);body.append(old)}
  if(run.error)body.append(el('p',run.error,'review-notice'));
}
function renderEfficiency(body,e,run){
  const f=e.efficiency,s=el('section',undefined,'evaluation-group');s.append(el('h3','호출 효율'));const stats=el('div',undefined,'stats-grid');
  for(const [label,value] of [['모델 요청',f.model_calls==null?'미기록':f.model_calls+'회'],['저장된 도구 실행',f.actual_calls+'회'],['참조 호출','미설정'],['소요 시간',f.elapsed_ms==null?'미기록':(f.elapsed_ms/1000).toFixed(1)+'초'],['SDK 추정 비용',f.sdk_estimated_usd==null?'미기록':'$'+f.sdk_estimated_usd.toFixed(4)],['불필요한 반복',f.unnecessary_calls==null?'미평가':f.unnecessary_calls+'회']]){
    const box=el('div');box.append(el('span',label),el('strong',value));stats.append(box);
  }
  s.append(stats,el('p',f.reference_reason+' 비용은 SDK의 기록된 추정치이며 실제 청구액이 아닙니다.','muted'));
  for(const r of e.unnecessary_calls){const item=el('div',undefined,'check'),b=el('button','호출 확인');b.onclick=()=>showEvidence(run.run_id,r.tool_run_id);item.append(el('p',r.reason),b);s.append(item)}
  s.append(link('실제 도구 호출 순서 보기 →',run.analysis_url+'#tools'));body.append(s);
}
async function selectRun(id,push=true){
  const ticket=++selection;$('#detail').setAttribute('aria-busy','true');
  try{const detail=await request('/api/cq-benchmark/detail?'+new URLSearchParams({run_id:id}));if(ticket!==selection)return;
    if(!matrix||matrix.version!==versionId(detail.run)){const value=await request('/api/cq-benchmark/matrix?'+new URLSearchParams({version:versionId(detail.run)}));if(ticket!==selection)return;matrix=value}
    renderDetail(detail);if(push)history.pushState(null,'',detail.benchmark_url+'&'+new URLSearchParams({version:matrix.version}))}
  catch(e){if(ticket===selection)$('#detail').replaceChildren(el('h2','실행을 불러올 수 없습니다.'),el('p',e.message))}
  finally{if(ticket===selection)$('#detail').removeAttribute('aria-busy')}
}
function support(){
  const target=$('#overview');target.replaceChildren();const d=el('details');d.id='capabilities';d.append(el('summary','도구 '+(data.tool_capabilities?.registered_count||0)+'개 · 지원 범위'));
  for(const t of data.tool_capabilities?.tools||[]){const item=el('p');item.append(el('strong',t.name+' · '),document.createTextNode(t.purpose+' — '+(t.limitation||'기재된 기능 구현')));d.append(item)}target.append(d);
}
async function load(){try{
  data=await request('/api/cq-benchmark');$('#notice').textContent='CQ별 공통 검사, 분석 품질, 종료조건과 호출 효율을 확인합니다. 과거 검토와 새 계약의 판정을 구분합니다.';
  $('#metrics').replaceChildren();for(const [label,value] of [['평가 대상',data.cases.length+'개 CQ'],['저장된 실행',data.runs.length+'회'],['계산 재현','제외'],['자료 활용 80%','미측정']]){const box=el('div',label,'metric');box.append(el('strong',value));$('#metrics').append(box)}
  support();const query=new URLSearchParams(location.search),id=query.get('run_id')||current?.run_id||'';
  const version=query.get('version')||(id?versionId(data.runs.find(r=>r.run_id===id)):'');await chooseVersion(version,id,false);
}catch(e){$('#notice').textContent=e.message}}
$('#versionSelect').onchange=()=>chooseVersion($('#versionSelect').value);$('#refresh').onclick=load;$('#closeEvidence').onclick=()=>$('#evidence').close();window.addEventListener('popstate',()=>{const query=new URLSearchParams(location.search);chooseVersion(query.get('version')||'',query.get('run_id')||'',false)});load();
