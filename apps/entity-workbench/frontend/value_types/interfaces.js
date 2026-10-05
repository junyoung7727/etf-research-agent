'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state,token,selected=new URLSearchParams(location.search).get('interface')||'Actor',clean='',busy=false,createKind;
const current=()=>state?.catalog.interfaces.find(i=>i.name===selected);
const dirty=()=>state&&JSON.stringify(state.catalog)!==clean;
const message=text=>{$('notice').textContent=text;$('notice').hidden=!text;};
const pathAttr=path=>' data-path="'+esc(JSON.stringify(path))+'"';
function options(values,selected){return values.map(v=>{const [value,label]=Array.isArray(v)?v:[v,v];return '<option value="'+esc(value)+'" '+(value===selected?'selected':'')+'>'+esc(label)+'</option>';}).join('');}
function select(path,values,value,extra=''){return '<select'+pathAttr(path)+extra+'>'+options(values,value)+'</select>';}
function textarea(path,value){return '<textarea rows="2" maxlength="4000"'+pathAttr(path)+'>'+esc(value)+'</textarea>';}
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':token},body:JSON.stringify(body)}:{});const result=await r.json();if(!r.ok)throw Error(result.error||'요청 실패');return result;}
function status(){
 document.querySelector('main').inert=busy;
 const changed=dirty();$('saveState').textContent=busy?'처리 중…':changed?'저장하지 않은 변경':state.pendingCount?'로컬 저장 v'+state.revision:'라이브러리 원본';
 $('save').disabled=busy||!changed||state.sourceChanged;
 $('applyLibrary').disabled=busy||changed||!state.pendingCount||state.sourceChanged||!state.validation.valid;
 $('reload').disabled=busy;
 $('sourceState').textContent='미반영 '+state.pendingCount+'개 · '+(state.sourceChanged?'원본 변경됨 · 비교 필요':'원본 일치')+' · '+state.libraryPath;
 $('definitionJson').textContent=JSON.stringify(current()||{},null,2);
}
async function load(){
 if(dirty()&&!confirm('저장하지 않은 변경을 버리고 최신 정의를 불러올까요?'))return;
 try{const [s,incoming]=await Promise.all([api('/api/status'),api('/api/interfaces')]);token=s.token;state=incoming;clean=JSON.stringify(state.catalog);render();message(state.sourceChanged?'객체·관계 또는 인터페이스 원본이 변경되었습니다. 초안을 내보내고 원본과 비교하세요.':state.validation.error||'');}
 catch(e){message(e.message);$('saveState').textContent='불러오기 실패';}
}
function navigation(){const q=$('typeSearch').value.toLowerCase();$('typeCount').textContent=state.catalog.interfaces.length;$('typeList').innerHTML=state.catalog.interfaces.filter(i=>(i.name+' '+i.description).toLowerCase().includes(q)).map(i=>'<button class="type-item" data-interface="'+esc(i.name)+'" aria-current="'+(i.name===selected)+'"><b>'+esc(i.name)+'</b><span class="count">'+Object.keys(i.implementations).length+'</span><small>'+esc(Object.keys(i.implementations).join(' · ')||'구현 객체 필요')+'</small></button>').join('');}
function render(){
 if(!current())selected=state.catalog.interfaces[0]?.name;
 navigation();const s=current();for(const id of ['addProperty','addLink','addImplementation','removeType'])$(id).disabled=!s;
 if(!s){$('typeTitle').textContent='인터페이스를 추가하세요.';for(const id of ['definitionFields','properties','links','implementations','typeMeta','contractSummary','originalJson','objectChoice'])$(id).replaceChildren();status();return;}
 $('typeTitle').textContent=s.name;$('typeMeta').textContent='공통 계약 · '+Object.keys(s.implementations).length+'개 객체가 구현';
 $('contractSummary').innerHTML=Object.keys(s.implementations).map(n=>'<span class="badge">'+esc(n)+' → '+esc(s.name)+'</span>').join('');
 $('definitionFields').innerHTML='<label>Display name · English</label><input type="text" maxlength="200"'+pathAttr(['displayName'])+' value="'+esc(s.displayName)+'"><label>Description · English</label>'+textarea(['description'],s.description);
 $('properties').innerHTML='<table><thead><tr><th>속성</th><th>타입</th><th>NULL 허용</th><th>의미 · English</th><th></th></tr></thead><tbody>'+Object.entries(s.properties).map(([n,p])=>'<tr data-property="'+esc(n)+'"><td><code>'+esc(n)+'</code></td><td>'+select(['properties',n,'dataType'],state.dataTypes,p.dataType)+'</td><td><input aria-label="'+esc(n)+' NULL 허용" type="checkbox"'+pathAttr(['properties',n,'nullable'])+(p.nullable?' checked':'')+(n==='id'?' disabled':'')+'></td><td>'+textarea(['properties',n,'description'],p.description)+'</td><td>'+(n==='id'?'PK':'<button data-remove="property" data-name="'+esc(n)+'">삭제</button>')+'</td></tr>').join('')+'</tbody></table>';
 const targets=[...Object.keys(state.objects).map(n=>['object:'+n,'Object · '+n]),...state.catalog.interfaces.map(i=>['interface:'+i.name,'Interface · '+i.name])];
 $('links').innerHTML=Object.entries(s.links).map(([n,l])=>'<div class="contract-link" data-link="'+esc(n)+'"><div class="link-head"><b>'+esc(n)+'</b><button data-remove="link" data-name="'+esc(n)+'">삭제</button></div><div class="link-fields"><label>대상'+select(['links',n,'target'],targets,l.target.kind+':'+l.target.name,' data-value-kind="target"')+'</label><label>개수'+select(['links',n,'cardinality'],['ONE','MANY'],l.cardinality)+'</label><label>구현 필수<input type="checkbox"'+pathAttr(['links',n,'required'])+(l.required?' checked':'')+'></label></div><label>관계의 의미 · English</label>'+textarea(['links',n,'description'],l.description)+'</div>').join('')||'<p class="helper">공통 관계 없음</p>';
 const available=Object.keys(state.objects).filter(n=>!s.implementations[n]);$('objectChoice').innerHTML=options([['','객체 선택'],...available],'');
 $('implementations').innerHTML=Object.entries(s.implementations).map(([n,impl])=>{
   const obj=state.objects[n];if(!obj)return '<p class="helper">미정의 구현 객체: '+esc(n)+'</p>';
   const props=Object.entries(obj.properties).map(([p,d])=>[p,p+' · '+d.dataType+(d.nullable?' · NULL':'')]);
   const linkOptions=[['','매핑 없음']];
   for(const [id,r] of Object.entries(state.links)){
     if(r.source===n)linkOptions.push([id+'|forward',r.definition.name+' → '+r.definition.target+' · 정방향']);
     if(r.definition.target===n)linkOptions.push([id+'|reverse',(r.definition.inverse?.displayName||r.definition.name)+' → '+r.source+' · 역방향']);
   }
   return '<details open class="implementation" data-object="'+esc(n)+'"><summary>'+esc(n)+' implements '+esc(s.name)+'</summary><div class="table-wrap"><table><thead><tr><th>공통 속성</th><th>실제 객체 속성</th></tr></thead><tbody>'+Object.keys(s.properties).map(p=>'<tr><td>'+esc(p)+'</td><td>'+select(['implementations',n,'properties',p],[['','속성 선택'],...props],impl.properties[p]||'',' aria-label="'+esc(n+'.'+p)+'"')+(obj.properties[impl.properties[p]]?.mappingStatus&&obj.properties[impl.properties[p]].mappingStatus!=='ready'?'<span class="mapping-status">원본 상태: '+esc(obj.properties[impl.properties[p]].mappingStatus)+'</span>':'')+'</td></tr>').join('')+'</tbody></table></div><div class="table-wrap"><table><thead><tr><th>공통 관계</th><th>실제 링크와 탐색 방향</th></tr></thead><tbody>'+Object.keys(s.links).map(l=>'<tr><td>'+esc(l)+'</td><td>'+select(['implementations',n,'links',l],linkOptions,impl.links[l]?impl.links[l].linkType+'|'+impl.links[l].direction:'',' data-value-kind="mapping" aria-label="'+esc(n+'.'+l)+'"')+'</td></tr>').join('')+'</tbody></table></div><button data-remove="implementation" data-name="'+esc(n)+'">구현 해제</button></details>';
 }).join('')||'<p class="helper">저장하려면 구현 객체와 매핑을 추가하세요.</p>';
 $('originalJson').textContent=JSON.stringify(state.sourceCatalog.interfaces.find(i=>i.name===s.name)||{},null,2);status();
}
function edit(e){
 const el=e.target;if(!el.dataset.path)return;
 const path=JSON.parse(el.dataset.path);let target=current();for(const key of path.slice(0,-1))target=target[key];const key=path.at(-1);
 if(el.dataset.valueKind==='mapping'){if(!el.value)delete target[key];else{const [linkType,direction]=el.value.split('|');target[key]={linkType,direction};}}
 else if(el.dataset.valueKind==='target'){const [kind,name]=el.value.split(':');target[key]={kind,name};}
 else target[key]=el.type==='checkbox'?el.checked:el.value;
 status();
}
document.querySelector('.workspace').addEventListener('input',edit);
document.querySelector('.workspace').addEventListener('change',e=>{if(e.target.tagName==='SELECT')edit(e);});
$('typeList').onclick=e=>{const b=e.target.closest('[data-interface]');if(b){selected=b.dataset.interface;history.replaceState(null,'','?interface='+encodeURIComponent(selected));render();}};
$('typeSearch').oninput=navigation;
document.querySelector('.workspace').addEventListener('click',e=>{
 const b=e.target.closest('[data-remove]');if(!b)return;const s=current(),n=b.dataset.name;
 if(b.dataset.remove==='property'){delete s.properties[n];for(const i of Object.values(s.implementations))delete i.properties[n];}
 if(b.dataset.remove==='link'){delete s.links[n];for(const i of Object.values(s.implementations))delete i.links[n];}
 if(b.dataset.remove==='implementation')delete s.implementations[n];render();
});
function create(kind){createKind=kind;$('createForm').reset();$('createTitle').textContent=kind==='interface'?'인터페이스 추가':kind==='property'?'공통 속성 추가':'공통 관계 추가';$('createError').textContent='';$('createDialog').showModal();$('createName').focus();}
$('addType').onclick=()=>create('interface');$('addProperty').onclick=()=>create('property');$('addLink').onclick=()=>create('link');$('cancelCreate').onclick=()=>$('createDialog').close();
$('createForm').onsubmit=e=>{
 e.preventDefault();const name=$('createName').value,description=$('createDescription').value,s=current();
 if(createKind==='interface'){
   if(state.objects[name]||state.catalog.interfaces.some(i=>i.name===name)||!/[A-Z]/.test(name[0])){$('createError').textContent='대문자로 시작하는 중복 없는 이름이 필요합니다.';return;}
   state.catalog.interfaces.push({formatVersion:1,name,displayName:name,description,properties:{id:{dataType:'String',nullable:false,description:'Identifier of the concrete object, preserved without conversion.'}},links:{},implementations:{}});selected=name;
 }else{
   const fields=createKind==='property'?s.properties:s.links;if(fields[name]){$('createError').textContent='같은 이름이 이미 있습니다.';return;}
   if(createKind==='property'){fields[name]={dataType:'String',nullable:true,description};for(const i of Object.values(s.implementations))i.properties[name]='';}
   else fields[name]={target:{kind:'object',name:Object.keys(state.objects)[0]},cardinality:'MANY',required:true,description};
 }
 $('createDialog').close();render();
};
$('addImplementation').onclick=()=>{const n=$('objectChoice').value;if(!n)return;const s=current(),obj=state.objects[n];s.implementations[n]={properties:Object.fromEntries(Object.keys(s.properties).map(p=>[p,p==='id'?obj.primaryKey:obj.properties[p]?p:''])),links:{}};render();};
$('removeType').onclick=()=>{if(confirm(current().name+' 인터페이스 정의를 삭제할까요? 실제 객체는 삭제되지 않습니다.')){state.catalog.interfaces=state.catalog.interfaces.filter(i=>i.name!==selected);render();}};
async function persist(apply){
 busy=true;status();try{state=await api('/api/interfaces'+(apply?'/apply':''),{catalog:state.catalog,revision:state.revision,sourceHash:state.sourceHash});clean=JSON.stringify(state.catalog);render();message(apply?'라이브러리 정의에 반영했습니다. 객체 모델을 다시 열면 구현 정보가 표시됩니다.':'계약과 매핑 검증을 통과해 초안을 저장했습니다.');}catch(e){message(e.message);}finally{busy=false;status();}
}
$('save').onclick=()=>persist(false);$('applyLibrary').onclick=()=>persist(true);$('reload').onclick=load;
$('export').onclick=()=>{if(!state)return;const url=URL.createObjectURL(new Blob([JSON.stringify(state.catalog,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='interface-contracts.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
addEventListener('beforeunload',e=>{if(dirty()||busy){e.preventDefault();e.returnValue='';}});
load();
