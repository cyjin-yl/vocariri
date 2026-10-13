import {mkdir,copyFile,readdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const root=process.cwd();
await mkdir(path.join(root,'dist','src'),{recursive:true});
await copyFile(path.join(root,'index.html'),path.join(root,'dist','index.html'));
await writeFile(path.join(root,'dist','runtime-config.json'),JSON.stringify({renderer:null}));
for(const file of await readdir(path.join(root,'src'))){if(/\.(mjs|css)$/.test(file))await copyFile(path.join(root,'src',file),path.join(root,'dist','src',file));}
console.log('Built static editor assets in dist/');
