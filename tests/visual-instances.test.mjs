import test from 'node:test';
import assert from 'node:assert/strict';
import {project,evaluate,validate,visualLayers} from '../src/core.mjs';
import {toAE} from '../src/export.mjs';

function fixture(){
  const p=project('声\n夜');
  p.duration=6;
  p.tokens.forEach((t,i)=>Object.assign(t,{start:i,end:i+1,preset:'still-linear-1-hold'}));
  p.visualInstances=[
    {id:'echo-back',tokenId:'l0-w0',groupId:'echo',start:2,end:5,zIndex:-1,transform:{x:-200,alpha:.4}},
    {id:'lead',tokenId:'l0-w0',groupId:'lead',start:0,end:4,zIndex:2,transform:{x:120}},
    {id:'reply',tokenId:'l1-w0',groupId:'reply',start:1,end:3,zIndex:1,transform:{y:100}},
  ];
  return p;
}

test('repeated and overlapping lyric instances outlive vocal ends without changing timing',()=>{
  const p=fixture(),before=structuredClone(p);
  assert.deepEqual(validate(p,{timed:true}),[]);
  const active=evaluate(p,2.5);
  assert.deepEqual(active.map(g=>g.id),['echo-back','reply','lead']);
  assert.deepEqual(active.map(g=>g.tokenId),['l0-w0','l1-w0','l0-w0']);
  assert.equal(active[0].alpha,.4);
  assert.equal(active[2].x,p.width/2+120);
  assert.deepEqual(evaluate(p,4.5).map(g=>g.id),['echo-back']);
  assert.deepEqual(evaluate(p,5),[]);
  assert.deepEqual(p,before);
});

test('layout membership is independent of paint order and independent groups',()=>{
  const p=fixture();
  p.visualInstances[0].groupId='pair';p.visualInstances[2].groupId='pair';
  delete p.visualInstances[0].transform;delete p.visualInstances[2].transform;
  const before=evaluate(p,2.5),positions=new Map(before.map(g=>[g.id,g.x]));
  assert.ok(positions.get('echo-back')<positions.get('reply'));
  p.visualInstances[0].zIndex=10;
  const after=evaluate(p,2.5);
  assert.equal(after.at(-1).id,'echo-back');
  for(const g of after)assert.equal(g.x,positions.get(g.id));
});

test('per-instance scene-time curves and transforms survive arbitrary seeking',()=>{
  const p=fixture();
  p.visualInstances[1].tracks={x:[{time:0,value:900,interpolation:'linear'},{time:4,value:1300}]};
  p.visualInstances[1].transform={x:10,y:20,scale:2,rotation:90};
  const a=evaluate(p,2.5).find(g=>g.id==='lead');
  assert.ok(Math.abs(a.x-(p.width/2+10))<1e-8);
  assert.ok(Math.abs(a.y-(p.height/2+20+(1150-p.width/2)*2))<1e-8);
  evaluate(p,4.5);assert.deepEqual(evaluate(p,2.5).find(g=>g.id==='lead'),a);
  assert.notEqual(evaluate(p,2.5)[0].x,a.x);
});

test('empty authoritative instance list does not fall back to vocal tokens',()=>{
  const p=fixture();p.visualInstances=[];
  assert.deepEqual(evaluate(p,.5),[]);assert.deepEqual(visualLayers(p),[]);
  delete p.visualInstances;assert.equal(evaluate(p,.5).length,1);
});

test('legacy projects remain readable, but cannot silently carry version 2 composition',()=>{
  const p=fixture();p.version=1;
  assert.match(validate(p).join('\n'),/version 2/);
  delete p.visualInstances;assert.deepEqual(validate(p,{timed:true}),[]);
  assert.equal(evaluate(p,.5).length,1);
});

test('invalid references, duplicate identity and malformed curves fail validation',()=>{
  const mutate=[
    p=>p.visualInstances[0].tokenId='missing',
    p=>p.visualInstances[0].id='lead',
    p=>p.visualInstances[0].end=7,
    p=>p.visualInstances[0].groupId='',
    p=>p.visualInstances[0].transform={scale:0},
    p=>p.visualInstances[0].tracks={x:[null]},
    p=>p.visualInstances[0].tracks={x:[{time:0,value:0,interpolation:'typo'}]},
  ];
  for(const change of mutate){const p=fixture();change(p);assert.ok(validate(p).length);assert.throws(()=>toAE(p));}
});

test('AE baked data retains separate editable layers, windows and compositing order',()=>{
  const p=fixture(),script=toAE(p);
  const data=JSON.parse(script.match(/var d=(.*);\napp.beginUndoGroup/)[1]);
  assert.deepEqual(data.layers.map(l=>l.id),['echo-back','reply','lead']);
  assert.deepEqual(data.layers.map(l=>[l.start,l.end]),[[2,5],[1,3],[0,4]]);
  const frame=evaluate(p,2.5);
  for(const layer of data.layers){
    const baked=layer.frames.find(f=>f[0]===2.5),g=frame.find(g=>g.id===layer.id);
    assert.deepEqual(baked,[2.5,g.x,g.y,g.scaleX*100,g.scaleY*100,g.rotation,g.alpha*100]);
  }
});

test('AE bake budget counts repeated visual layers instead of only vocal tokens',()=>{
  const p=fixture();p.duration=100000;p.fps=10;
  assert.throws(()=>toAE(p),/glyph-frames/);
});
