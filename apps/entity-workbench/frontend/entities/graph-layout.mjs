// Layout the complete expanded population; render only the current viewport.
export const CARD={width:196,height:72,stepX:224,stepY:108,padding:28,top:144};
const INITIALS='ㄱㄱㄴㄷㄷㄹㅁㅂㅂㅅㅅㅇㅈㅈㅊㅋㅌㅍㅎ';
const GROUPS=['0–9',...'ABCDEFGHIJKLMNOPQRSTUVWXYZ',...'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ','기타'];
const nameCollator=new Intl.Collator('ko-KR',{numeric:true,sensitivity:'base'});
export function nameGroup(name){
 const first=String(name??'').normalize('NFKC').trim().charAt(0),code=first.charCodeAt(0);
 if(/[0-9]/.test(first))return '0–9';
 if(/[a-z]/i.test(first))return first.toUpperCase();
 if(code>=0xac00&&code<=0xd7a3)return INITIALS[Math.floor((code-0xac00)/588)];
 return '기타';
}
export function indexedCatalog(catalog){
 const rows=[...catalog.rows].sort((a,b)=>GROUPS.indexOf(nameGroup(a.display_name))-GROUPS.indexOf(nameGroup(b.display_name))||nameCollator.compare(a.display_name,b.display_name)||String(a.entity_id).localeCompare(String(b.entity_id)));
 const groups=[];
 rows.forEach((row,index)=>{const label=nameGroup(row.display_name);if(groups.at(-1)?.label===label)groups.at(-1).count++;else groups.push({label,index,count:1});});
 return {...catalog,rows,groups};
}
export function displayCount(total,zoom,width,height){
 if(!total)return 0;
 const capacity=Math.max(1,Math.floor(width/CARD.stepX)*Math.floor(height/CARD.stepY));
 const base=Math.min(total,capacity);
 const progress=Math.max(0,Math.min(1,(zoom-85)/95));
 return Math.min(total,Math.round(base+(total-base)*progress*progress));
}
export function collectionLayout(count,width,height,vertical){
 const aspect=Math.max(.4,width/Math.max(height,1))*(vertical?.85:1.5);
 const columns=vertical?1:Math.max(1,Math.ceil(Math.sqrt(Math.max(1,count)*aspect*CARD.stepY/CARD.stepX)));
 const rows=Math.ceil(count/columns);
 return {count,columns,rows,width:Math.max(396,columns*CARD.stepX+CARD.padding*2),height:rows*CARD.stepY+CARD.top+CARD.padding};
}
export function dictionaryLayout(count,groups){
 const bands=groups.filter(g=>g.index<count).map((g,row)=>({...g,count:Math.min(g.count,count-g.index),y:CARD.top+row*CARD.stepY}));
 const columns=Math.max(1,...bands.map(g=>g.count));
 return {count,bands,columns,rows:bands.length,width:columns*CARD.stepX+100,height:bands.length*CARD.stepY+CARD.top+CARD.padding};
}
export function positionOf(index,layout){
 if(layout.bands){const band=layout.bands.find(g=>index>=g.index&&index<g.index+g.count);return {x:80+(index-band.index)*CARD.stepX,y:band.y};}
 return {x:CARD.padding+(index%layout.columns)*CARD.stepX,y:CARD.top+Math.floor(index/layout.columns)*CARD.stepY};
}
export function visibleIndices(layout,left,top,width,height,scale){
 const x0=left/scale,y0=top/scale,x1=(left+width)/scale,y1=(top+height)/scale;
 if(layout.bands){const result=[];for(const band of layout.bands){if(band.y+CARD.height<y0-108||band.y>y1+108)continue;const start=Math.max(0,Math.floor((x0-80)/CARD.stepX)-1),end=Math.min(band.count-1,Math.ceil((x1-80)/CARD.stepX)+1);for(let c=start;c<=end;c++)result.push(band.index+c);}return result;}
 const startColumn=Math.max(0,Math.floor((x0-CARD.padding)/CARD.stepX)-1);
 const endColumn=Math.min(layout.columns-1,Math.ceil((x1-CARD.padding)/CARD.stepX)+1);
 const startRow=Math.max(0,Math.floor((y0-CARD.top)/CARD.stepY)-1);
 const endRow=Math.min(layout.rows-1,Math.ceil((y1-CARD.top)/CARD.stepY)+1);
 const result=[];
 for(let r=startRow;r<=endRow;r++)for(let c=startColumn;c<=endColumn;c++){
  const index=r*layout.columns+c;if(index<layout.count)result.push(index);
 }
 return result;
}
