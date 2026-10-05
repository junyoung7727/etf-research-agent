const {test}=require('node:test');
const assert=require('node:assert/strict');
const {project}=require('../frontend/puppygraph/exploration.js');
const node=(type,id)=>({key:JSON.stringify([type,id]),type,id,properties:{}});
const [a,b,newsA,newsB,shared,event]=[node('Equity','A'),node('Equity','B'),node('NewsArticle','A-only'),node('NewsArticle','B-only'),node('NewsArticle','shared'),node('SourceEvent','event')];
const edge=(key,source,target,role='')=>({key,source:source.key,target:target.key,type:source.type+'_Link_'+target.type,properties:{roleCode:role}});
const edges=[edge('a',newsA,a),edge('b',newsB,b),edge('sa',shared,a),edge('sb',shared,b),edge('event',newsA,event),edge('role',newsA,a,'buyer')];
function fixture(){return {nodes:new Map([a,b,newsA,newsB,shared,event].map(n=>[n.key,n])),edges:new Map(edges.map(e=>[e.key,e])),rootsExpanded:new Set(),rootTypes:['Equity'],expanded:new Set(),scopes:new Map([[a.key,{edgeKeys:new Set(['a','sa','role'])}],[b.key,{edgeKeys:new Set(['b','sb'])}],[newsA.key,{edgeKeys:new Set(['a','role','event'])}]]),mode:'all',root:null};}
const records=s=>[...project(s).nodes.values()].filter(n=>!n.group).map(n=>n.key).sort();
test('A raw-data type cannot reveal rows without a concrete parent',()=>{
 const s=fixture();s.rootsExpanded.add('NewsArticle');
 // Even a stale or malformed type expansion cannot bypass the root-type restriction.
 assert.deepEqual(records(s),[]);assert.equal([...project(s).nodes.values()].find(n=>n.type==='NewsArticle').expandable,false);
});
test('Expanding stocks alone keeps news folded; A opens only its own news',()=>{
 const s=fixture();s.rootsExpanded.add('Equity');assert.deepEqual(records(s),[a.key,b.key].sort());
 s.expanded.add(a.key);assert.deepEqual(records(s),[a.key,b.key,newsA.key,shared.key].sort());
 assert(!records(s).includes(newsB.key));
});
test('Shared rows keep one identity, and collapsing A preserves B’s independently open rows',()=>{
 const s=fixture();s.rootsExpanded.add('Equity');s.expanded.add(a.key);s.expanded.add(b.key);
 assert.equal(records(s).filter(key=>key===shared.key).length,1);
 s.expanded.delete(a.key);assert.deepEqual(records(s),[a.key,b.key,newsB.key,shared.key].sort());
});
test('Nested branches disappear when their only visible ancestor is folded',()=>{
 const s=fixture();s.rootsExpanded.add('Equity');s.expanded.add(a.key);s.expanded.add(newsA.key);
 assert(records(s).includes(event.key));s.expanded.delete(a.key);assert(!records(s).includes(event.key));
 s.expanded.add(a.key);assert(records(s).includes(event.key));
});
test('Direction, role and identities survive every fold state without phantom links',()=>{
 const s=fixture();s.rootsExpanded.add('Equity');s.expanded.add(a.key);
 const p=project(s),actual=p.edges.get('a');assert.equal(actual.source,newsA.key);assert.equal(actual.target,a.key);
 assert.equal(p.edges.get('role').properties.roleCode,'buyer');
 assert.deepEqual([...p.edges.values()].filter(e=>!e.membership).flatMap(e=>e.originalKeys||[e.key]).sort(),edges.map(e=>e.key).sort());
 for(const e of p.edges.values()){assert(p.nodes.has(e.source));assert(p.nodes.has(e.target));}
});
test('Single-object mode keeps the concrete root visible and folds its neighbors',()=>{
 const s=fixture();s.mode='one';s.root=a;assert.deepEqual(records(s),[a.key]);
 s.expanded.add(a.key);assert.deepEqual(records(s),[a.key,newsA.key,shared.key].sort());
});
