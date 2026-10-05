import test from 'node:test';
import assert from 'node:assert/strict';
import {displayCount, collectionLayout, visibleIndices, positionOf} from '../frontend/entities/graph-layout.mjs';
import {indexedCatalog,nameGroup,dictionaryLayout} from '../frontend/entities/graph-layout.mjs';

test('dictionary mode gives each initial its own horizontal row, including offscreen members',()=>{
 const groups=[{label:'A',index:0,count:200},{label:'B',index:200,count:2},{label:'ㄱ',index:202,count:300}];
 const layout=dictionaryLayout(502,groups);
 assert.equal(positionOf(0,layout).y,positionOf(199,layout).y);
 assert(positionOf(199,layout).x>positionOf(0,layout).x);
 assert.equal(positionOf(0,layout).x,positionOf(200,layout).x);
 assert(positionOf(200,layout).y>positionOf(199,layout).y);
 const last=positionOf(501,layout);
 assert(visibleIndices(layout,last.x,last.y,600,400,1).includes(501));
 assert(visibleIndices(layout,0,0,600,400,1).length<30);
 assert.equal(dictionaryLayout(201,groups).bands.at(-1).count,1);
});

test('name index groups Korean initials and sorts naturally without losing duplicate names',()=>{
 const rows=['하나','삼성','까치','가나','alpha10','Alpha2','2기업','10기업','삼성'].map((display_name,i)=>({display_name,entity_id:String(i)}));
 const result=indexedCatalog({rows,total:rows.length});
 assert.deepEqual(result.rows.map(r=>r.display_name),['2기업','10기업','Alpha2','alpha10','가나','까치','삼성','삼성','하나']);
 assert.deepEqual(result.groups.map(g=>g.label),['0–9','A','ㄱ','ㅅ','ㅎ']);
 assert.equal(result.groups.find(g=>g.label==='ㅅ').count,2);
 assert.equal(nameGroup('가나'),'ㄱ');
 assert.equal(rows[0].display_name,'하나');
});

test('zoom progressively reveals the real population, including every company at maximum',()=>{
 let last=0;
 for(let z=85;z<=180;z++){
  const count=displayCount(2766,z,640,400);
  assert(count>=last && count<=2766);last=count;
 }
 assert.equal(last,2766);
 assert.equal(displayCount(2400,180,400,300),2400);
 assert(displayCount(2766,120,1200,800)>displayCount(2766,120,400,300));
 assert.equal(displayCount(0,180,600,400),0);
});

test('all expanded nodes have distinct positions and the final company is reachable by scrolling',()=>{
 const layout=collectionLayout(2766,640,400,true);
 const positions=Array.from({length:2766},(_,i)=>positionOf(i,layout));
 assert.equal(new Set(positions.map(p=>`${p.x}:${p.y}`)).size,2766);
 assert(layout.width<=640 && layout.height>400);
 assert.equal(layout.columns,1,'Default name order must read downward without horizontal navigation');
 assert(positions.every((p,i)=>p.x===positions[0].x && (!i||p.y>positions[i-1].y)));
 const last=positions.at(-1);
 const visible=visibleIndices(layout,last.x,last.y,640,400,1);
 assert(visible.includes(2765));assert(visible.length<100);
 const visited=new Set();
 for(let y=0;y<layout.height;y+=300)for(let x=0;x<layout.width;x+=500){
  visibleIndices(layout,x,y,640,400,1).forEach(i=>visited.add(i));
 }
 assert.equal(visited.size,2766);
});
