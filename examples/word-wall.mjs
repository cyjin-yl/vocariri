// Original experimental renderer. It illustrates unrestricted code authoring,
// not an artist-reviewed template or a recreation of any referenced PV.
export const capabilities={ae:'raster-only',reason:'Repeated stroked word bands are not mapped to editable AE layers by this module.'};
let foreground;
export function draw({canvas,project:p,time,options,baseDraw,core}){
  baseDraw(canvas,{...p,tokens:[]},time,options);
  foreground ||= document.createElement('canvas');
  baseDraw(foreground,p,time,{...options,alpha:true});
  const ctx=canvas.getContext('2d');
  const active=p.tokens.find(t=>t.start!==null&&time>=t.start&&time<(t.end??p.duration));
  if(!active){ctx.drawImage(foreground,0,0);return;}
  const text=p.tokens.filter(t=>t.line===active.line).map(t=>t.text).join('');
  const phase=time-(p.tokens.find(t=>t.line===active.line)?.start??0);
  const size=p.height*.16;ctx.save();ctx.font=`900 ${size}px ${p.font}`;ctx.textBaseline='middle';ctx.textAlign='left';ctx.strokeStyle=p.color;ctx.lineWidth=Math.max(1,size*.014);ctx.globalAlpha=.22;
  const width=ctx.measureText(text+'  ').width;
  for(let row=-1;row<8;row++){const drift=(phase*70*(row%2?1:-1))%Math.max(width,1);for(let i=-2;i<Math.ceil(p.width/Math.max(width,1))+2;i++)ctx.strokeText(text,i*width+drift,row*size*.93);}
  ctx.restore();ctx.drawImage(foreground,0,0);
}
