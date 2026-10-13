import {evaluate,cameraAt,validate,visualLayers} from './core.mjs';
export function toAE(p){
  const errors=validate(p,{timed:true});if(errors.length)throw Error(errors.join('\n'));
  // Bake affine motion at project frame rate. Text metrics differ between Canvas and AE;
  // the importer recenters each actual AE text rectangle, but line spacing needs review.
  const frames=Math.ceil(p.duration*p.fps),visual=visualLayers(p);if(frames*visual.length>2000000)throw Error('AE bake exceeds 2,000,000 glyph-frames; split into scenes');
  const layers=visual.map(t=>({...t,frames:[]})).sort((a,b)=>(a.zIndex??0)-(b.zIndex??0)),lookup=new Map(layers.map(l=>[l.id,l]));const cameras=[];
  for(let n=0;n<frames;n++){const time=n/p.fps;const c=cameraAt(p,time);cameras.push([time,c.x,c.y,c.zoom,c.rotation]);for(const g of evaluate(p,time))lookup.get(g.id).frames.push([time,g.x,g.y,g.scaleX*100,g.scaleY*100,g.rotation,g.alpha*100]);}
  const data={width:p.width,height:p.height,fps:p.fps,duration:p.duration,font:p.font,fontSize:p.fontSize,color:p.color,title:p.title,layers,cameras};
  return `/* Vocariri study build. Editable text + baked 2D camera null.
AE rendering parity is not yet verified. Background/portrait/audio are not embedded.
Use the original media, install matching fonts, then save the resulting .aep.
Canvas and AE font metrics may differ. Frame-rate baking preserves sampled geometry.
*/
(function(){
var d=${JSON.stringify(data)};
app.beginUndoGroup("Vocariri import");
try {
if(!app.project)app.newProject();
var comp=app.project.items.addComp(d.title,d.width,d.height,1,d.duration,d.fps);
var cam=comp.layers.addNull(d.duration);cam.name="Vocariri 2D camera";
cam.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([d.width/2,d.height/2]);
for(var c=0;c<d.cameras.length;c++){var k=d.cameras[c],tr=cam.property("ADBE Transform Group");tr.property("ADBE Position").setValueAtTime(k[0],[d.width/2+k[1],d.height/2+k[2]]);tr.property("ADBE Scale").setValueAtTime(k[0],[k[3]*100,k[3]*100]);tr.property("ADBE Rotate Z").setValueAtTime(k[0],k[4]);}
for(var i=0;i<d.layers.length;i++){
var source=d.layers[i],layer=comp.layers.addText(source.text);layer.name=source.id+" "+source.text;
var doc=layer.property("ADBE Text Properties").property("ADBE Text Document").value;
doc.font=d.font;doc.fontSize=d.fontSize;doc.applyFill=true;doc.applyStroke=false;doc.justification=ParagraphJustification.CENTER_JUSTIFY;
doc.fillColor=[parseInt(d.color.substr(1,2),16)/255,parseInt(d.color.substr(3,2),16)/255,parseInt(d.color.substr(5,2),16)/255];
layer.property("ADBE Text Properties").property("ADBE Text Document").setValue(doc);
var box=layer.sourceRectAtTime(0,false),t=layer.property("ADBE Transform Group");t.property("ADBE Anchor Point").setValue([box.left+box.width/2,box.top+box.height/2]);
layer.parent=cam;layer.inPoint=Math.ceil(source.start*d.fps)/d.fps;layer.outPoint=Math.min(d.duration,Math.ceil(source.end*d.fps)/d.fps);
for(var f=0;f<source.frames.length;f++){var v=source.frames[f];t.property("ADBE Position").setValueAtTime(v[0],[v[1],v[2]]);t.property("ADBE Scale").setValueAtTime(v[0],[v[3],v[4]]);t.property("ADBE Rotate Z").setValueAtTime(v[0],v[5]);t.property("ADBE Opacity").setValueAtTime(v[0],v[6]);}
}
comp.openInViewer();
}finally{app.endUndoGroup();}
})();\n`;
}
