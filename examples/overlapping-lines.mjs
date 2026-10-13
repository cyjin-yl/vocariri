// Explicit CLI transform: node cli.mjs transform timed.json examples/overlapping-lines.mjs out.json
// Data-only project loading never imports this module automatically.
export default function({project:p}){
  p.version=2;
  p.visualInstances=[];
  for(const line of new Set(p.tokens.map(t=>t.line))){
    const tokens=p.tokens.filter(t=>t.line===line);
    if(tokens.some(t=>t.start===null||t.end===null))throw Error('Finish lyric timing first');
    const end=Math.min(p.duration,Math.max(...tokens.map(t=>t.end))+.8);
    for(const t of tokens){
      p.visualInstances.push({id:`lead:${t.id}`,tokenId:t.id,groupId:`line:${line}`,
        start:t.start,end,zIndex:10,transform:{y:line%2?80:-80}});
      const echoStart=t.start+.25;
      if(echoStart<end)p.visualInstances.push({id:`echo:${t.id}`,tokenId:t.id,groupId:`echo-line:${line}`,
        start:echoStart,end,zIndex:0,transform:{y:line%2?110:-50,x:20,alpha:.25}});
    }
  }
  return p;
}
