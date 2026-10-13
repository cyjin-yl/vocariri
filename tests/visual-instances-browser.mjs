import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {serve} from '../cli.mjs';
import {mkdir,writeFile} from 'node:fs/promises';

const server=await serve(0),browser=await chromium.launch({channel:'chromium',headless:true});
try{
  const page=await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForFunction(()=>!!window.vocariri);
  const result=await page.evaluate(async()=>{
    const {project}=await import('/src/core.mjs');
    const p=project('A');p.width=640;p.height=360;p.duration=5;p.fontSize=100;
    Object.assign(p.tokens[0],{start:0,end:1,preset:'still-linear-1-hold'});
    p.visualInstances=[
      {id:'left-copy',tokenId:'l0-w0',groupId:'left',start:1,end:3,transform:{x:-150}},
      {id:'right-copy',tokenId:'l0-w0',groupId:'right',start:2,end:4,transform:{x:150}},
    ];
    window.vocariri.setProject(p);
    function sample(time){
      window.vocariri.render(time,true);
      const pixels=document.getElementById('preview').getContext('2d').getImageData(0,0,640,360).data;
      let left=0,right=0;
      for(let y=0;y<360;y++)for(let x=0;x<640;x++)if(pixels[(y*640+x)*4+3]){if(x<320)left++;else right++;}
      return {left,right};
    }
    const overlap=sample(2.5),after=sample(3.5),empty=sample(4);
    return {overlap,after,empty,vocalEnd:window.vocariri.project.tokens[0].end};
  });
  assert.ok(result.overlap.left>0&&result.overlap.right>0);
  assert.equal(result.after.left,0);assert.ok(result.after.right>0);
  assert.deepEqual(result.empty,{left:0,right:0});assert.equal(result.vocalEnd,1);
  await mkdir('test-results',{recursive:true});
  await writeFile('test-results/visual-instances-browser.json',JSON.stringify(result,null,2));
  console.log('Browser render: independent overlapping instances and transparent exit passed.');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
