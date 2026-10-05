// Presentation only: ELK receives graph IDs and measured rectangles, never source mappings.
export const CARD_WIDTH=300;
export const CARD_HEIGHT=100;
export const LINK_FONT='800 14px "Malgun Gothic", sans-serif';

export async function layoutModel(model,{engine,measureLabel=text=>text.length*9,positions}={}){
 if(!model.objects.length&&!model.relations.length)return {nodes:[],edges:[],bounds:{x:0,y:0,width:0,height:0}};
 const children=model.objects.map(o=>({id:o.id,width:CARD_WIDTH,height:CARD_HEIGHT,ports:[],...(positions?.get(o.id)?{x:positions.get(o.id).x,y:positions.get(o.id).y}:{})}));
 const nodes=new Map(children.map(n=>[n.id,n]));
 const edges=model.relations.map((r,i)=>{
  for(const id of [r.source,r.target])if(!nodes.has(id))throw Error(`Missing relationship endpoint: ${id}`);
  const from=`port:${i}:from`,to=`port:${i}:to`;
  nodes.get(r.source).ports.push({id:from,width:0,height:0});
  nodes.get(r.target).ports.push({id:to,width:0,height:0});
  const text=`${r.label} · ${r.cardinality}`;
  return {id:r.id,sources:[from],targets:[to],labels:[{id:`label:${i}`,text,width:Math.ceil(measureLabel(text))+16,height:24}]};
 });
 const result=await engine.layout({id:'schema',children,edges,layoutOptions:{
  'elk.algorithm':'layered',
  'elk.direction':'RIGHT',
  'elk.edgeRouting':'ORTHOGONAL',
  'elk.randomSeed':'7',
  'elk.padding':'[top=30,left=30,bottom=30,right=30]',
  'elk.spacing.nodeNode':'32',
  'elk.spacing.edgeNode':'24',
  'elk.spacing.edgeEdge':'18',
  'elk.spacing.labelNode':'20',
  'elk.spacing.labelLabel':'12',
  'elk.layered.spacing.nodeNodeBetweenLayers':'100',
  'elk.layered.spacing.edgeNodeBetweenLayers':'24',
  'elk.layered.spacing.edgeEdgeBetweenLayers':'18',
  'elk.layered.nodePlacement.strategy':'NETWORK_SIMPLEX',
  'elk.layered.mergeEdges':'false',
  'elk.layered.thoroughness':'20',
  'elk.edgeLabels.placement':'CENTER',
  'elk.spacing.edgeLabel':'8',
  ...(positions?{'elk.layered.layering.strategy':'INTERACTIVE','elk.layered.crossingMinimization.strategy':'INTERACTIVE','elk.layered.nodePlacement.strategy':'INTERACTIVE'}:{}),
 }});
 return {
  nodes:result.children.map(({id,x,y,width,height})=>({id,x,y,width,height})),
  edges:result.edges.map(e=>{
   if(e.sections?.length!==1||!e.labels?.length)throw Error(`Missing relationship route: ${e.id}`);
   const s=e.sections[0],l=e.labels[0];
   return {id:e.id,points:[s.startPoint,...(s.bendPoints||[]),s.endPoint],label:{x:l.x,y:l.y,width:l.width,height:l.height,text:l.text}};
  }),
  bounds:{x:0,y:0,width:result.width,height:result.height},
 };
}

export function edgePath(points){
 return points.map((p,i)=>`${i?'L':'M'}${p.x} ${p.y}`).join(' ');
}

export function connectedModel(model,id){
 const relations=model.relations.filter(r=>r.source===id||r.target===id);
 const ids=new Set([id,...relations.flatMap(r=>[r.source,r.target])]);
 return {objects:model.objects.filter(o=>ids.has(o.id)),relations};
}
