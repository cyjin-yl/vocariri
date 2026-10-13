#!/usr/bin/env node
import {readFile,writeFile,mkdir,stat} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import * as core from './src/core.mjs';
import {project,validate,presets,evaluate,applyPreset} from './src/core.mjs';
import {toAE} from './src/export.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
export async function serve(port=4173,{renderer=null}={}){const mime={'.html':'text/html','.mjs':'text/javascript','.css':'text/css','.json':'application/json'};const server=createServer(async(req,res)=>{
  try{const url=new URL(req.url,'http://localhost');if(url.pathname==='/runtime-config.json'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({renderer:renderer?'/custom-renderer.mjs':null}));return;}if(url.pathname==='/custom-renderer.mjs'&&renderer){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(await readFile(path.resolve(renderer)));return;}const rel=decodeURIComponent(url.pathname)==='/'?'index.html':decodeURIComponent(url.pathname).slice(1);const file=path.resolve(root,rel);if(file!==root&&!file.startsWith(root+path.sep))throw Error('path');if(!['index.html','src'].some(x=>rel===x||rel.startsWith(x+'/')))throw Error('path');const bytes=await readFile(file);res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});res.end(bytes);}catch{res.writeHead(404);res.end('Not found');}});await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve);});return server;}
async function load(file,timed=false){const p=JSON.parse(await readFile(file,'utf8'));const errors=validate(p,{timed});if(errors.length)throw Error(errors.join('\n'));return p;}
async function main(){const [cmd,...args]=process.argv.slice(2);
  if(cmd==='serve'){const rendererIndex=args.indexOf('--renderer');const renderer=rendererIndex>=0?args[rendererIndex+1]:null;const server=await serve(Number(args[0]&&!args[0].startsWith('--')?args[0]:4173),{renderer});console.log(`Vocariri: http://127.0.0.1:${server.address().port}`);}
  else if(cmd==='init'){const p=project(await readFile(args[0],'utf8'));await writeFile(args[1]||'project.vocariri.json',JSON.stringify(p,null,2),{flag:'wx'});}
  else if(cmd==='validate'){const p=await load(args[0],args.includes('--timed'));console.log(JSON.stringify({valid:true,tokens:p.tokens.length,version:p.version}));}
  else if(cmd==='presets'){console.log(JSON.stringify(presets,null,2));}
  else if(cmd==='sample'){console.log(JSON.stringify(evaluate(await load(args[0]),Number(args[1]||0)),null,2));}
  else if(cmd==='apply'){const p=await load(args[0]);applyPreset(p,args[1],args[3]?.split(','));await writeFile(args[2],JSON.stringify(p,null,2),{flag:'wx'});}
  else if(cmd==='transform'){const p=await load(args[0]);const module=await import(pathToFileURL(path.resolve(args[1])).href);if(typeof module.default!=='function')throw Error('Module requires a default function');const result=await module.default({project:structuredClone(p),core});const errors=validate(result);if(errors.length)throw Error(errors.join('\n'));await writeFile(args[2],JSON.stringify(result,null,2),{flag:'wx'});}
  else if(cmd==='export-ae'){
    const p=await load(args[0],true),ri=args.indexOf('--renderer');let script;
    if(ri<0)script=toAE(p);
    else{const {chromium}=await import('playwright');const server=await serve(0,{renderer:args[ri+1]});let browser;try{browser=await chromium.launch({channel:'chromium',headless:true});const page=await browser.newPage();await page.goto(`http://127.0.0.1:${server.address().port}`);await page.waitForFunction(()=>!!window.vocariri);await page.evaluate(p=>window.vocariri.setProject(p),p);script=await page.evaluate(()=>window.vocariri.exportAE());}finally{await browser?.close();await new Promise(r=>server.close(r));}}
    if(typeof script!=='string')throw Error('AE adapter must return JSX text');await writeFile(args[1],script,{flag:'wx'});
  }
  else if(cmd==='render'){
    const p=await load(args[0],true),dir=path.resolve(args[1]||'exports/frames');const {chromium}=await import('playwright');const rendererIndex=args.indexOf('--renderer');const server=await serve(0,{renderer:rendererIndex>=0?args[rendererIndex+1]:null});let browser;
    try{browser=await chromium.launch({channel:'chromium',headless:true});const page=await browser.newPage();await page.goto(`http://127.0.0.1:${server.address().port}`);await page.waitForFunction(()=>!!window.vocariri);await page.evaluate(p=>window.vocariri.setProject(p),p);await page.evaluate(()=>document.fonts.ready);await mkdir(dir,{recursive:true});const limit=args.includes('--one')?1:Math.ceil(p.duration*p.fps);const transparent=!args.includes('--opaque');
      for(let i=0;i<limit;i++){const data=await page.evaluate(({time,transparent})=>window.vocariri.render(time,transparent),{time:i/p.fps,transparent});await writeFile(path.join(dir,`${String(i).padStart(6,'0')}.png`),Buffer.from(data.split(',')[1],'base64'),{flag:'wx'});}
      await writeFile(path.join(dir,'render.json'),JSON.stringify({frames:limit,fps:p.fps,width:p.width,height:p.height,alpha:transparent,media:'text-only; images and audio not loaded by this renderer',font:p.font},null,2),{flag:'wx'});console.log(JSON.stringify({frames:limit,output:dir}));
    }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
  }else{console.log('vocariri serve [port] [--renderer module.mjs]\nvocariri init lyrics.txt project.json\nvocariri validate project.json [--timed]\nvocariri presets\nvocariri sample project.json seconds\nvocariri apply input.json preset-id output.json [token-id,token-id]\nvocariri transform input.json module.mjs output.json\nvocariri export-ae project.json output.jsx\nvocariri render project.json output-dir [--one] [--opaque] [--renderer module.mjs]');if(cmd)process.exitCode=1;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(e=>{console.error(e.message);process.exitCode=1;});
