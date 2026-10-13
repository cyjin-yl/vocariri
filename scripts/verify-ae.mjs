import {spawn}from'node:child_process';import{readFile,writeFile,mkdir,open,stat}from'node:fs/promises';import path from'node:path';import{toAE}from'../src/export.mjs';
const [input,outdir,aePath]=process.argv.slice(2);
if(!input||!outdir||!aePath)throw Error('Usage: node scripts/verify-ae.mjs project.json new-output-directory path-to-AfterFX.com');
const dir=path.resolve(outdir);await mkdir(dir,{recursive:false});const p=JSON.parse(await readFile(input,'utf8'));const posix=x=>x.replaceAll('\\','/');
const outputProject=posix(path.join(dir,'project.aep')),frame=posix(path.join(dir,'frame.png')),report=posix(path.join(dir,'report.txt'));
let jsx=toAE(p).replace('if(!app.project)app.newProject();','app.newProject();').replace('comp.openInViewer();',`app.project.save(new File(${JSON.stringify(outputProject)}));\ncomp.saveFrameToPng(${Math.min(2.5,p.duration/2)},new File(${JSON.stringify(frame)}));`);
jsx=`app.beginSuppressDialogs();\ntry {\n${jsx}\nvar r=new File(${JSON.stringify(report)}); r.encoding="UTF-8";if(r.open("w")){r.writeln("SAVED_AND_RENDERED");r.close();}\n} catch(error) {\nvar r=new File(${JSON.stringify(report)});r.encoding="UTF-8";if(r.open("w")){r.writeln("FAILED "+error.toString()+" line="+error.line);r.close();}\n} finally {\n// The output AEP was explicitly saved above. Discard only later test/render state.\nif(app.project)app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);\napp.endSuppressDialogs(false);\napp.quit();\n}\n`;
const script=path.join(dir,'verify.jsx');await writeFile(script,jsx);
if(process.platform!=='win32')throw Error('The native launch adapter is currently Windows-only; JSX remains portable to AE on macOS');
// Explicit user preference: minimize AE, never forcibly terminate it. The launcher
// observes exit only; timeout leaves the application and recovery state untouched.
const psQuote=s=>"'"+s.replaceAll("'","''")+"'";
const launcher=path.join(dir,'launch.ps1');
await writeFile(launcher,`$taskAe = Start-Process -FilePath ${psQuote(path.resolve(aePath))} -WorkingDirectory ${psQuote(path.dirname(path.resolve(aePath)))} -ArgumentList @('-m','-r',${psQuote('"'+script+'"')}) -WindowStyle Minimized -RedirectStandardOutput ${psQuote(path.join(dir,'process.log'))} -RedirectStandardError ${psQuote(path.join(dir,'stderr.log'))} -PassThru\n$taskAe.Id | Set-Content -LiteralPath ${psQuote(path.join(dir,'process-id.txt'))}\n$taskAe.WaitForExit()\nexit $taskAe.ExitCode\n`);
const proc=spawn('powershell.exe',['-NoProfile','-File',launcher],{windowsHide:true,stdio:'ignore'});let timeout;
try{const result=await Promise.race([new Promise((resolve,reject)=>{proc.once('error',reject);proc.once('exit',code=>resolve({code}));}),new Promise(resolve=>{timeout=setTimeout(()=>resolve({timedOut:true}),180000);})]);
 if(result.timedOut){proc.unref();await writeFile(path.join(dir,'verification.json'),JSON.stringify({complete:false,processExited:false,reason:'Timeout; AE was left intact, never forcibly terminated'}));throw Error('AE did not exit within 180 seconds; left intact for normal in-app closure');}
 const reportText=await readFile(path.join(dir,'report.txt'),'utf8');if(!reportText.includes('SAVED_AND_RENDERED'))throw Error(reportText);await stat(path.join(dir,'project.aep'));await stat(path.join(dir,'frame.png'));await writeFile(path.join(dir,'verification.json'),JSON.stringify({saved:true,rendered:true,processExited:true,exitCode:result.code,savePolicy:'Save AEP, discard only subsequent test state, close project, quit',launch:'minimized'},null,2));console.log(JSON.stringify({saved:true,rendered:true,processExited:true,exitCode:result.code}));
}finally{clearTimeout(timeout);}
