import {evaluate,cameraAt,backgroundScale} from './core.mjs';
export function draw(canvas,p,time,{background=null,portrait=null,alpha=false}={}){
  if(canvas.width!==p.width)canvas.width=p.width;if(canvas.height!==p.height)canvas.height=p.height;
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,p.width,p.height);
  if(!alpha){ctx.fillStyle=p.background;ctx.fillRect(0,0,p.width,p.height);}
  const c=cameraAt(p,time);ctx.save();ctx.translate(p.width/2+c.x,p.height/2+c.y);ctx.rotate(c.rotation*Math.PI/180);ctx.scale(c.zoom,c.zoom);ctx.translate(-p.width/2,-p.height/2);
  if(!alpha&&background){const s=backgroundScale(p.width,p.height,c,background.width,background.height);ctx.drawImage(background,p.width/2-background.width*s/2,p.height/2-background.height*s/2,background.width*s,background.height*s);}
  if(!alpha&&portrait){const s=p.height*.9/portrait.height;ctx.drawImage(portrait,p.width/2-portrait.width*s/2,p.height-portrait.height*s,portrait.width*s,portrait.height*s);}
  ctx.font=`${p.fontSize}px ${p.font}`;
  const items=evaluate(p,time,(text,size)=>{ctx.font=`${size}px ${p.font}`;return ctx.measureText(text).width;});
  for(const g of items){ctx.save();ctx.translate(g.x,g.y);ctx.rotate(g.rotation*Math.PI/180);ctx.scale(g.scaleX,g.scaleY);ctx.globalAlpha=g.alpha;ctx.font=`${g.fontSize}px ${p.font}`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=p.color;ctx.fillText(g.text,0,0);ctx.restore();}
  ctx.restore();return items;
}
