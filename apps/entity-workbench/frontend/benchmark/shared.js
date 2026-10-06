window.CQ=(()=>{
  function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node}
  async function request(url){const r=await fetch(url);const value=await r.json();if(!r.ok)throw new Error(value.error||'조회 실패');return value}
  const labels={pass:'통과',fail:'실패',unknown:'판정 보류',not_evaluated:'미평가',review_needed:'검토 필요',incomplete:'실행 미완료'};
  function statusLabel(value){return labels[value]||value}
  function badge(value){return el('span',statusLabel(value),'badge '+value)}
  function json(target,value){
    target.replaceChildren();const text=typeof value==='string'?value:JSON.stringify(value,null,2);
    const regex=/"(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g;
    let end=0;for(const m of text.matchAll(regex)){target.append(document.createTextNode(text.slice(end,m.index)));const v=m[0];target.append(el('span',v,'json-'+(v.endsWith(':')?'key':v.startsWith('"')?'string':/true|false|null/.test(v)?'literal':'number')));end=m.index+v.length}target.append(document.createTextNode(text.slice(end)));
  }
  let evidenceRequest=0;
  async function showEvidence(run,id){const ticket=++evidenceRequest,body=document.querySelector('#evidenceBody');body.textContent='불러오는 중…';const dialog=document.querySelector('#evidence');if(!dialog.open)dialog.showModal();
    try{const value=await request('/api/cq-benchmark/evidence?'+new URLSearchParams({run_id:run,tool_run_id:id}));if(ticket===evidenceRequest)json(body,value)}catch(e){if(ticket===evidenceRequest)body.textContent=e.message}}
  function answer(target,text){
    for(const line of (text||'저장된 답변이 없습니다.').split('\n')){
      if(!line.trim())continue;const h=/^(#{1,4})\s+(.+)/.exec(line),n=el(h?'h'+Math.min(h[1].length+1,4):'p'),value=h?h[2]:line;
      for(const [i,part] of value.split('**').entries())n.append(i%2?el('strong',part):document.createTextNode(part));target.append(n);
    }
  }
  return {el,request,json,showEvidence,statusLabel,badge,answer};
})();
