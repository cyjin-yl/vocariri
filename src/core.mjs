export const VERSION = 2;
export const clamp = (x, lo=0, hi=1) => Math.max(lo, Math.min(hi, x));
export const families = ['still','rise','fall','slide','diagonal','pop','compress','stretch','turn','swing','orbit','wave','scatter','jitter','pulse','drift','cascade','recoil','fan','snap'];
const rhythms = ['soft','linear','sharp','elastic'];
const endings = ['fade','hold','lift','shrink'];
export const presets = families.flatMap(family => rhythms.flatMap(ease => [0.35,0.65,1,1.5].flatMap(amount => endings.map(exit => ({id:`${family}-${ease}-${amount}-${exit}`,family,ease,amount,exit,label:`${family} / ${ease} / ${amount} / ${exit}`,review:'procedural-unreviewed'})))));
export function tokenize(text) {
  const gs = new Intl.Segmenter('ja',{granularity:'grapheme'});
  return text.split(/\r?\n/).flatMap((line, li) => {
    // A pipe explicitly separates romanized syllables or user-defined groups.
    const parts = line.includes('|') ? line.split('|').map(x=>x.trim()).filter(Boolean) : (line.match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]|[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*|[^\s]/gu)||[]);
    return parts.flatMap(part => (/^[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]+$/u.test(part)&&!line.includes('|')) ? [...gs.segment(part)].map(x=>x.segment):[part]).map((text,i)=>({id:`l${li}-w${i}`,line:li,text,start:null,end:null,explicitEnd:false,preset:presets[0].id}));
  });
}
export function project(text='声が\n夜を越える') {return {version:VERSION,title:'Untitled',width:1920,height:1080,fps:30,duration:12,font:'sans-serif',fontSize:108,color:'#f3eee5',background:'#151515',layout:'line',retention:'word',tracking:14,seed:1,tokens:tokenize(text),camera:[{time:0,x:0,y:0,zoom:1,rotation:0}],link:'smooth',customTracks:{}};}
export function validate(p,{timed=false}={}) {
  const errors=[];
  if(![1,VERSION].includes(p?.version)) errors.push('Unsupported project version');
  for(const k of ['width','height','fps','duration','fontSize']) if(!Number.isFinite(p?.[k])||p[k]<=0)errors.push(`${k} must be positive`);
  if(p.width>8192||p.height>8192||p.fps>120)errors.push('Maximum output is 8192 pixels and 120 fps');
  if(!Array.isArray(p?.tokens))return [...errors,'tokens must be an array'];
  const ids=new Set(); let previous=-Infinity;
  for(const t of p.tokens){
    if(typeof t.id!=='string'||!t.id.length)errors.push('Token requires a stable ID');
    if(typeof t.text!=='string'||!t.text.length||!Number.isInteger(t.line)||t.line<0)errors.push('Invalid token text or line');
    if(ids.has(t.id))errors.push(`Duplicate token ${t.id}`);ids.add(t.id);
    if((t.start!==null&&(!Number.isFinite(t.start)||t.start<0))||(t.end!==null&&!Number.isFinite(t.end)))errors.push(`Invalid timestamp: ${t.id}`);
    if(timed&&(t.start===null||t.end===null))errors.push(`Untimed token: ${t.id}`);
    if(t.start!==null&&t.end!==null&&(t.end<=t.start||t.end>p.duration+1e-6))errors.push(`Invalid range: ${t.id}`);
    if(t.start!==null&&t.start<previous)errors.push(`Nonchronological token: ${t.id}`);
    if(t.start!==null)previous=t.start;
    if(!presets.some(x=>x.id===t.preset))errors.push(`Unknown preset: ${t.id}`);
  }
  let ct=-Infinity;
  if(!Array.isArray(p.camera)||!p.camera.length) errors.push('camera requires at least one key');
  else for(const k of p.camera){if(!['time','x','y','zoom','rotation'].every(n=>Number.isFinite(k[n]))||k.zoom<=0||k.time<0||k.time<=ct)errors.push('Invalid camera key');ct=k.time;}
  if(!['smooth','cut'].includes(p.link))errors.push('Unknown continuity mode');
  if(!['line','column','diagonal','grid','hero','arc'].includes(p.layout))errors.push('Unknown layout');
  if(p.retention!==undefined&&!['word','line'].includes(p.retention))errors.push('Unknown retention mode');
  if(!Number.isFinite(p.tracking)||!Number.isFinite(p.seed))errors.push('Invalid tracking or seed');
  for(const [id,tracks] of Object.entries(p.customTracks||{})){
    if(!ids.has(id))errors.push(`Unknown custom track token: ${id}`);
    for(const [name,keys]of Object.entries(tracks)){
      if(!['x','y','scaleX','scaleY','rotation','alpha'].includes(name)||!Array.isArray(keys)||!keys.length){errors.push(`Invalid track: ${name}`);continue;}
      let prev=-Infinity;for(const k of keys){if(!Number.isFinite(k.time)||!Number.isFinite(k.value)||k.time<=prev)errors.push(`Invalid custom key: ${id}`);prev=k.time;}
    }
  }
  errors.push(...validateVisualInstances(p));
  return errors;
}
const visualTrackNames=['x','y','scaleX','scaleY','rotation','alpha'];
function validateVisualInstances(p){
  if(p.visualInstances===undefined)return [];
  if(p.version!==VERSION)return ['Independent visual instances require project version 2'];
  if(!Array.isArray(p.visualInstances))return ['visualInstances must be an array'];
  const errors=[],ids=new Set(),tokens=new Set(p.tokens.map(t=>t.id));
  for(const v of p.visualInstances){
    if(!v||typeof v!=='object'){errors.push('Invalid visual instance');continue;}
    if(typeof v.id!=='string'||!v.id.length||ids.has(v.id))errors.push('Visual instances require unique stable IDs');
    ids.add(v.id);
    if(!tokens.has(v.tokenId))errors.push(`Unknown visual token: ${v.tokenId}`);
    if(typeof v.groupId!=='string'||!v.groupId.length)errors.push(`Visual instance requires a layout group: ${v.id}`);
    if(!Number.isFinite(v.start)||!Number.isFinite(v.end)||v.start<0||v.end<=v.start||v.end>p.duration)errors.push(`Invalid visual range: ${v.id}`);
    if(v.zIndex!==undefined&&!Number.isFinite(v.zIndex))errors.push(`Invalid visual zIndex: ${v.id}`);
    if(v.preset!==undefined&&!presets.some(x=>x.id===v.preset))errors.push(`Unknown visual preset: ${v.id}`);
    if(v.transform!==undefined){
      if(!v.transform||typeof v.transform!=='object'||Array.isArray(v.transform))errors.push(`Invalid visual transform: ${v.id}`);
      else for(const [name,value] of Object.entries(v.transform)){
        if(!['x','y','scale','rotation','alpha'].includes(name)||!Number.isFinite(value)||(name==='scale'&&value<=0)||(name==='alpha'&&(value<0||value>1)))errors.push(`Invalid visual transform ${name}: ${v.id}`);
      }
    }
    if(v.tracks!==undefined){
      if(!v.tracks||typeof v.tracks!=='object'||Array.isArray(v.tracks)){errors.push(`Invalid visual tracks: ${v.id}`);continue;}
      for(const [name,keys] of Object.entries(v.tracks)){
        if(!visualTrackNames.includes(name)||!Array.isArray(keys)||!keys.length){errors.push(`Invalid visual track ${name}: ${v.id}`);continue;}
        let previous=-Infinity;
        for(const k of keys){
          if(!k||!Number.isFinite(k.time)||!Number.isFinite(k.value)||k.time<0||k.time>p.duration||k.time<=previous||!['soft','linear','hold','hermite',undefined].includes(k.interpolation)||['inTangent','outTangent'].some(n=>k[n]!==undefined&&!Number.isFinite(k[n])))errors.push(`Invalid visual key: ${v.id}`);
          previous=k?.time;
        }
      }
    }
  }
  return errors;
}
export class TimingSession {
  constructor(p){this.p=p;this.focus=0;this.active=null;this.undoStack=[];this.redoStack=[];}
  snapshot(){return JSON.stringify({tokens:this.p.tokens,focus:this.focus,active:this.active});}
  restore(s){Object.assign(this,JSON.parse(s));this.p.tokens=this.tokens;delete this.tokens;}
  edit(fn){const before=this.snapshot();fn();if(before!==this.snapshot()){this.undoStack.push(before);this.redoStack=[];}}
  undo(){if(this.undoStack.length){this.redoStack.push(this.snapshot());this.restore(this.undoStack.pop());}}
  redo(){if(this.redoStack.length){this.undoStack.push(this.snapshot());this.restore(this.redoStack.pop());}}
  start(time){
    if(!Number.isFinite(time)||time<0||time>=this.p.duration)throw Error('打点超出音频范围');
    const t=this.p.tokens[this.focus];if(!t)return;
    const prev=this.p.tokens[this.focus-1],next=this.p.tokens[this.focus+1];
    if(prev?.start!==null&&prev?.start!==undefined&&time<=prev.start)throw Error('开始时间必须晚于上一字');
    if(next?.start!==null&&next?.start!==undefined&&time>=next.start)throw Error('开始时间必须早于下一字');
    if(prev?.explicitEnd&&prev.end>time)throw Error('与上一字显式结束时间冲突，请先修改结束点');
    this.edit(()=>{
      if(prev&&prev.start!==null&&!prev.explicitEnd)prev.end=time;
      t.start=time;if(t.end!==null&&t.end<=time){t.end=null;t.explicitEnd=false;}
      if(next?.start!==null&&next?.start!==undefined&&!t.explicitEnd)t.end=next.start;
      this.active=this.focus;this.focus=Math.min(this.p.tokens.length,this.focus+1);
    });
  }
  end(time){const t=this.p.tokens[this.active];if(!t||t.start===null)throw Error('先用 [ 标记一个字的开始');
    const next=this.p.tokens[this.active+1];
    if(!Number.isFinite(time)||time<=t.start||time>this.p.duration||(next?.start!=null&&time>next.start))throw Error('结束时间必须位于当前字开始之后、下一字之前');
    this.edit(()=>{t.end=time;t.explicitEnd=true;this.active=null;});
  }
  select(index){this.focus=clamp(index,0,Math.max(0,this.p.tokens.length-1));this.active=null;return this.p.tokens[this.focus]?.start;}
  move(dir){let idx=clamp(this.focus,0,this.p.tokens.length-1);if(dir==='left')idx--;else if(dir==='right')idx++;else {const line=this.p.tokens[idx]?.line;const group=this.p.tokens.filter(t=>t.line===line);const col=group.findIndex(t=>t.id===this.p.tokens[idx]?.id);const target=this.p.tokens.filter(t=>t.line===line+(dir==='up'?-1:1));if(target.length)idx=this.p.tokens.indexOf(target[Math.min(col,target.length-1)]);}return this.select(idx);}
}
function ease(t,kind){t=clamp(t);if(kind==='linear')return t;if(kind==='sharp')return 1-(1-t)**5;if(kind==='elastic')return t===0||t===1?t:1-2**(-8*t)*Math.cos(t*9);return t*t*(3-2*t);}
export function cameraAt(p,time){const keys=p.camera;let a=keys[0],b=a;for(const k of keys){if(k.time<=time)a=k;else{b=k;break;}b=a;}const q=p.link==='cut'?0:ease((time-a.time)/(b.time-a.time||1),'soft');return Object.fromEntries(['x','y','zoom','rotation'].map(k=>[k,a[k]+(b[k]-a[k])*q]));}
export function backgroundScale(w,h,c,iw,ih){
  // Inverse-transform all viewport corners into image space; includes rotation and pan.
  if([w,h,iw,ih,c.zoom].some(x=>!Number.isFinite(x)||x<=0))throw Error('Invalid image/camera dimensions');
  const r=-c.rotation*Math.PI/180,co=Math.cos(r),si=Math.sin(r);let result=0;
  for(const x of [-w/2,w/2])for(const y of [-h/2,h/2]){const dx=(x-c.x)/c.zoom,dy=(y-c.y)/c.zoom;result=Math.max(result,2*Math.abs(dx*co-dy*si)/iw,2*Math.abs(dx*si+dy*co)/ih);}return result*1.002;
}
export function sampleTrack(keys,time){if(time<=keys[0].time)return keys[0].value;for(let i=1;i<keys.length;i++)if(time<keys[i].time){const a=keys[i-1],b=keys[i],dt=b.time-a.time,u=(time-a.time)/dt;
  if(a.interpolation==='hold')return a.value;
  if(a.interpolation==='linear')return a.value+(b.value-a.value)*u;
  if(a.interpolation==='hermite'){const m0=(a.outTangent??0)*dt,m1=(b.inTangent??0)*dt;return (2*u**3-3*u*u+1)*a.value+(u**3-2*u*u+u)*m0+(-2*u**3+3*u*u)*b.value+(u**3-u*u)*m1;}
  return a.value+(b.value-a.value)*ease(u,'soft');}return keys.at(-1).value;}
export function visualEnd(p,t){if(p.retention==='line')return Math.max(...p.tokens.filter(x=>x.line===t.line).map(x=>x.end??p.duration));return t.end??p.duration;}
// A visual instance references lyric identity, never rewrites the audio timings.
// Array order determines placement within a group; zIndex determines paint order.
export function visualLayers(p){
  if(p.visualInstances===undefined)return p.tokens.map(t=>({...t,end:visualEnd(p,t)}));
  const errors=validateVisualInstances(p);if(errors.length)throw Error(errors.join('\n'));
  const tokens=new Map(p.tokens.map(t=>[t.id,t]));
  return p.visualInstances.map(v=>({...tokens.get(v.tokenId),id:v.id,tokenId:v.tokenId,
    groupId:v.groupId,line:v.groupId,start:v.start,end:v.end,zIndex:v.zIndex??0,
    preset:v.preset??tokens.get(v.tokenId).preset,transform:v.transform,tracks:v.tracks}));
}
export function evaluate(p,time,measure=(s,size)=>[...s].length*size*.8){
  if(p.visualInstances===undefined)return evaluateTokens(p,time,measure);
  const layers=visualLayers(p),lookup=new Map(layers.map(v=>[v.id,v]));
  const customTracks=Object.fromEntries(layers.map(v=>[v.id,{...p.customTracks?.[v.tokenId],...v.tracks}]));
  return evaluateTokens({...p,tokens:layers,retention:'word',customTracks},time,measure).map(g=>{
    const v=lookup.get(g.id),tr=v.transform??{},scale=tr.scale??1,r=(tr.rotation??0)*Math.PI/180;
    const x=(g.x-p.width/2)*scale,y=(g.y-p.height/2)*scale;
    return {...g,tokenId:v.tokenId,instanceId:v.id,groupId:v.groupId,zIndex:v.zIndex,
      x:p.width/2+x*Math.cos(r)-y*Math.sin(r)+(tr.x??0),
      y:p.height/2+x*Math.sin(r)+y*Math.cos(r)+(tr.y??0),
      scaleX:g.scaleX*scale,scaleY:g.scaleY*scale,rotation:g.rotation+(tr.rotation??0),
      alpha:clamp(g.alpha*(tr.alpha??1))};
  }).sort((a,b)=>a.zIndex-b.zIndex);
}
function evaluateTokens(p,time,measure){
  const result=[];const lines=[...new Set(p.tokens.map(x=>x.line))];
  for(const line of lines){const tokens=p.tokens.filter(x=>x.line===line),widths=tokens.map(t=>measure(t.text,p.fontSize));const total=widths.reduce((a,b)=>a+b,0)+p.tracking*(tokens.length-1);const fit=Math.min(1,p.width*.86/Math.max(total,1));let cursor=-total*fit/2;
    tokens.forEach((t,i)=>{
      const baseX=cursor+widths[i]*fit/2;cursor+=(widths[i]+p.tracking)*fit;
      const end=visualEnd(p,t);if(t.start===null||time<t.start||time>=end)return;
      const preset=presets.find(x=>x.id===t.preset)||presets[0],d=Math.max(.001,end-t.start),age=time-t.start;
      const q=ease(age/Math.min(.32,d*.45),preset.ease),out=clamp((end-time)/Math.min(.20,d*.3)),v=(1-q)*preset.amount,A=90*v;
      let x=baseX,y=0,sx=1,sy=1,rot=0,alpha=q,layoutScale=fit;
      if(p.layout==='column'){layoutScale=Math.min(1,p.height*.8/(tokens.length*(p.fontSize+p.tracking)));x=0;y=(i-(tokens.length-1)/2)*(p.fontSize+p.tracking)*layoutScale;}
      if(p.layout==='diagonal'){y=baseX*.32;rot=-12;layoutScale*=.85;}
      if(p.layout==='grid'){const cols=Math.ceil(Math.sqrt(tokens.length*1.7)),rows=Math.ceil(tokens.length/cols);layoutScale=Math.min(1,p.width*.78/(cols*(Math.max(...widths)+p.tracking)),p.height*.78/(rows*(p.fontSize+p.tracking)));x=(i%cols-(cols-1)/2)*(Math.max(...widths)+p.tracking)*layoutScale;y=(Math.floor(i/cols)-(rows-1)/2)*(p.fontSize+p.tracking)*layoutScale;}
      if(p.layout==='hero'){x=0;y=0;layoutScale=Math.min(p.width*.8/Math.max(1,widths[i]),p.height*.72/p.fontSize);if(tokens.some(n=>n.start!==null&&n.start>t.start&&n.start<=time))alpha=0;}
      if(p.layout==='arc'){const angle=(i-(tokens.length-1)/2)/Math.max(1,tokens.length-1)*1.7;x=Math.sin(angle)*p.width*.36;y=(1-Math.cos(angle))*p.height*.5-p.height*.10;rot=angle*180/Math.PI;layoutScale=Math.min(fit,.9);}
      switch(preset.family){
        case'still':alpha=1;break;case'rise':y+=A;break;case'fall':y-=A;break;case'slide':x-=A*2;break;case'diagonal':x-=A;y+=A;break;
        case'pop':sx=sy=1+v*1.5;break;case'compress':sx=1-v*.8;sy=1+v;break;case'stretch':sx=1+v*2;sy=1-v*.6;break;
        case'turn':rot-=90*v;break;case'swing':rot+=Math.sin(age*16)*v*40;break;case'orbit':x+=Math.cos(age*12)*A;y+=Math.sin(age*12)*A;break;
        case'wave':y+=Math.sin(age*10+i*.7)*A;break;case'scatter':x+=Math.sin(i*7.13+p.seed)*A*3;y+=Math.cos(i*3.71+p.seed)*A*2;rot+=v*(i%2?35:-35);break;
        case'jitter':x+=Math.sin(Math.floor(age*24)*78.2+i)*A*.4;y+=Math.cos(Math.floor(age*24)*41.3+i)*A*.15;break;
        case'pulse':sx=sy=1+Math.sin(age*15)*v*.5;break;case'drift':x+=A*.35;y+=A*.2;rot+=v*8;break;
        case'cascade':y+=A*(1+i*.25);break;case'recoil':x+=Math.sin(age*15)*A*1.5;break;case'fan':rot+=(i-(tokens.length-1)/2)*v*20;y+=Math.abs(i-(tokens.length-1)/2)*A*.3;break;
        case'snap':x+=Math.round(v*4)*22;break;
      }
      if(preset.exit==='fade')alpha*=out;else if(preset.exit==='lift'){alpha*=out;y-=(1-out)*80;}else if(preset.exit==='shrink'){sx*=out;sy*=out;alpha*=out;}
      const item={id:t.id,text:t.text,x:p.width/2+x,y:p.height/2+y,scaleX:sx*layoutScale,scaleY:sy*layoutScale,rotation:rot,alpha:clamp(alpha),fontSize:p.fontSize,line};
      for(const [k,keys]of Object.entries(p.customTracks?.[t.id]||{}))item[k]=sampleTrack(keys,time);
      result.push(item);
    });
  }return result;
}
export function applyPreset(p,id,ids){if(!presets.some(x=>x.id===id))throw Error('Unknown preset');for(const t of p.tokens)if(!ids||ids.includes(t.id))t.preset=id;}
