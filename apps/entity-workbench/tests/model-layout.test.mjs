import test from 'node:test';
import assert from 'node:assert/strict';
import ELK from '../frontend/vendor/elk.bundled.js';
import {layoutModel,connectedModel} from '../frontend/objects/model-layout.mjs';

const object=id=>({id,label:id});
const relation=(id,source,target)=>({id,source,target,label:id,cardinality:'many-to-one'});
const overlaps=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
function verify(result,model){
 assert.deepEqual(result.nodes.map(n=>n.id).sort(),model.objects.map(n=>n.id).sort());
 assert.deepEqual(result.edges.map(e=>e.id).sort(),model.relations.map(e=>e.id).sort());
 for(const a of result.nodes)for(const b of result.nodes)if(a.id!==b.id)assert(!overlaps(a,b),`${a.id} overlaps ${b.id}`);
 for(const edge of result.edges){
  assert(edge.points.length>=2,`${edge.id} lost its route`);
  for(let i=1;i<edge.points.length;i++){
   const a=edge.points[i-1],b=edge.points[i];
   assert(a.x===b.x||a.y===b.y,`${edge.id} must use orthogonal segments`);
   for(const node of result.nodes){
    const inset={x:node.x+1,y:node.y+1,width:node.width-2,height:node.height-2};
    const segment={x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(b.x-a.x),height:Math.abs(b.y-a.y)};
    assert(!overlaps(inset,segment),`${edge.id} crosses ${node.id}`);
   }
  }
  const rel=model.relations.find(r=>r.id===edge.id);
  for(const [id,point] of [[rel.source,edge.points[0]],[rel.target,edge.points.at(-1)]]){
   const n=result.nodes.find(n=>n.id===id);
   assert(point.x>=n.x-1&&point.x<=n.x+n.width+1&&point.y>=n.y-1&&point.y<=n.y+n.height+1,`${edge.id} points to the wrong object`);
  }
  for(const node of result.nodes)assert(!overlaps(edge.label,node),`${edge.id} label covers ${node.id}`);
  for(const other of result.edges)if(other.id!==edge.id)assert(!overlaps(edge.label,other.label),`${edge.id} label covers ${other.id}`);
  for(const p of [...edge.points,edge.label,{x:edge.label.x+edge.label.width,y:edge.label.y+edge.label.height}]){
   assert(p.x>=0&&p.y>=0&&p.x<=result.bounds.width&&p.y<=result.bounds.height,'Fit must include arrows and labels');
  }
 }
}

test('cycles, inverse links, self loops and parallel links keep distinct routes and exact directions',async()=>{
 const model={objects:['Company','Equity','News','Event','Isolated'].map(object),relations:[
  relation('Issues','Company','Equity'),relation('IssuedBy','Equity','Company'),
  relation('Reports','News','Event'),relation('Mentions','News','Equity'),
  relation('Holds','Company','Equity'),relation('RepresentativeArticle','News','News'),
 ]};
 const before=JSON.stringify(model);
 const result=await layoutModel(model,{engine:new ELK()});
 verify(result,model);
 assert.equal(new Set(result.edges.map(e=>JSON.stringify(e.points))).size,model.relations.length,'Different relationships must remain individually traceable');
 assert.equal(JSON.stringify(model),before,'Layout must never change ontology definitions');
 assert.deepEqual(await layoutModel(model,{engine:new ELK()}),result,'Automatic layout should be stable');
 const positions=new Map(result.nodes.map(n=>[n.id,{...n}]));
 positions.get('Company').y+=160;
 positions.get('Company').x+=30;
 verify(await layoutModel(model,{engine:new ELK(),positions}),model);
});

test('a busy security hub leaves card interiors and label rectangles readable',async()=>{
 const model={objects:['Equity','ETF',...Array.from({length:10},(_,i)=>'Data'+i)].map(object),relations:[]};
 for(let i=0;i<10;i++)for(const target of ['Equity','ETF'])model.relations.push(relation(`ForSecurity${i}${target}`,'Data'+i,target));
 verify(await layoutModel(model,{engine:new ELK()}),model);
});

test('empty and isolated models are valid; broken endpoints fail visibly',async()=>{
 assert.deepEqual(await layoutModel({objects:[],relations:[]},{engine:new ELK()}),{nodes:[],edges:[],bounds:{x:0,y:0,width:0,height:0}});
 const model={objects:[object('Company')],relations:[]};
 verify(await layoutModel(model,{engine:new ELK()}),model);
 await assert.rejects(layoutModel({...model,relations:[relation('Broken','Company','Missing')]},{engine:new ELK()}),/Missing/);
});

test('connection focus includes every incoming/outgoing link, retaining inverses and self loops',()=>{
 const model={objects:['Company','Equity','News','Event'].map(object),relations:[relation('Issues','Company','Equity'),relation('IssuedBy','Equity','Company'),relation('Loop','Company','Company'),relation('Reports','News','Event')]};
 const subset=connectedModel(model,'Company');
 assert.deepEqual(subset.objects.map(o=>o.id),['Company','Equity']);
 assert.deepEqual(subset.relations.map(r=>r.id),['Issues','IssuedBy','Loop']);
 assert.equal(model.relations.length,4,'Focusing must not delete definitions');
});
