import {spawn}from'node:child_process';import{chromium}from'playwright';import assert from'node:assert/strict';import{writeFile}from'node:fs/promises';
const exe=process.argv[2];if(!exe)throw Error('Pass the compiled Tauri executable path');
const port=19387;
const proc=spawn(exe,[],{windowsHide:true,stdio:'ignore',env:{...process.env,VOCARIRI_TEST_MODE:'1',WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS:`--remote-debugging-port=${port} --remote-debugging-address=127.0.0.1`}});
let browser,page;try{
 for(let n=0;n<80;n++){try{browser=await chromium.connectOverCDP(`http://127.0.0.1:${port}`);break;}catch{await new Promise(r=>setTimeout(r,250));}}
 if(!browser)throw Error('WebView2 debug endpoint did not become ready');
 page=browser.contexts()[0].pages()[0];await page.waitForFunction(()=>!!window.vocariri);
 assert.ok((await page.url()).includes('tauri.localhost'));await page.locator('#demo').click();assert.ok(await page.evaluate(()=>window.vocariri.project.tokens.every(t=>t.start!==null)));
 await page.locator('#renderer-file').setInputFiles('examples/word-wall.mjs');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('已载入自定义'));
 await page.evaluate(()=>window.vocariri.seek(2.5));const encoded=await page.evaluate(()=>window.vocariri.render(2.5,true));assert.ok(encoded.startsWith('data:image/png;base64,'));await writeFile('test-results/tauri-frame.png',Buffer.from(encoded.split(',')[1],'base64'));
 await page.screenshot({path:'test-results/tauri-editor.png'});await writeFile('test-results/tauri.json',JSON.stringify({passed:true,platform:process.platform,checks:['native Tauri WebView2 launch','packaged static assets','core editor','explicit custom renderer','transparent PNG render'],notTested:['macOS','Linux','native media playback timing']},null,2));console.log('Tauri WebView2 smoke checks passed');
}finally{if(page){await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('finish_test')).catch(()=>{});}await browser?.close();const exited=await Promise.race([new Promise(r=>proc.once('exit',()=>r(true))),new Promise(r=>setTimeout(()=>r(false),5000))]);if(!exited){proc.unref();console.error('Test window did not close normally; process left intact.');process.exitCode=1;}}
