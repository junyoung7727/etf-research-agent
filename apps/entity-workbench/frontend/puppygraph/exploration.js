'use strict';
// Raw objects retain their typed IDs. Only visible, expanded instances can reveal neighbors.
const GraphExploration=(()=>{
 const typeKey=type=>JSON.stringify(['type-group',type]);
 function project(state){
  const nodes=new Map(),edges=new Map(),visible=new Set();
  if(state.mode==='one'&&state.root)visible.add(state.root.key);
  else for(const n of state.nodes.values())if(state.rootTypes.includes(n.type)&&state.rootsExpanded.has(n.type))visible.add(n.key);
  const queue=[...visible];
  for(let i=0;i<queue.length;i++){
   const owner=queue[i];if(!state.expanded.has(owner))continue;
   for(const key of state.scopes.get(owner)?.edgeKeys||[]){
    const e=state.edges.get(key),neighbor=e.source===owner?e.target:e.source;
    if(!visible.has(neighbor)){visible.add(neighbor);queue.push(neighbor);}
   }
  }
  for(const n of state.nodes.values()){
   if(visible.has(n.key))nodes.set(n.key,n);
   const isRoot=state.rootTypes.includes(n.type);
   if(!visible.has(n.key)||(isRoot&&state.mode==='all')){
    const key=typeKey(n.type);
    if(!nodes.has(key))nodes.set(key,{key,type:n.type,group:true,expandable:isRoot&&state.mode==='all',count:0});
    nodes.get(key).count++;
   }
  }
  if(state.mode==='all')for(const n of state.nodes.values()){
   const key=n.key;if(!state.rootTypes.includes(n.type)||!visible.has(key)||!state.rootsExpanded.has(n.type))continue;
   const member={key:JSON.stringify(['membership',key]),source:typeKey(n.type),target:key,membership:true};edges.set(member.key,member);
  }
  for(const e of state.edges.values()){
   const source=visible.has(e.source)?e.source:typeKey(state.nodes.get(e.source).type);
   const target=visible.has(e.target)?e.target:typeKey(state.nodes.get(e.target).type);
   if(source===e.source&&target===e.target){edges.set(e.key,e);continue;}
   const key=JSON.stringify(['summary',e.type,e.properties.roleCode||'',source,target]);
   if(!edges.has(key))edges.set(key,{...e,key,source,target,summary:true,originalKeys:[]});
   edges.get(key).originalKeys.push(e.key);
  }
  return {nodes,edges};
 }
 return {project,typeKey};
})();
if(typeof module!=='undefined')module.exports=GraphExploration;
