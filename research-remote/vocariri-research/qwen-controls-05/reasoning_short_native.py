import base64,json,time,urllib.request,urllib.error,shlex,hashlib
from pathlib import Path
root=Path(__file__).parent/'reasoning-short-native'
plan=json.loads((root/'plan.json').read_text())
clips=Path('/tank/shared/projects/vocariri-research/luna-public/outputs/qwen-short-native-06')
key=next(shlex.split(x.split('=',1)[1])[0] for x in Path('/etc/1cat-vllm.env').read_text().splitlines() if x.startswith('VLLM_API_KEY='))
for variant in plan['variants']:
 for item in json.loads((clips/'clips.json').read_text()):
  p=clips/item['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
  out=root/(variant['id']+'-'+p.stem+'.json')
  if out.exists():continue
  payload={'model':'[redacted model]','messages':[{'role':'user','content':[{'type':'text','text':'Describe the visible typography and its changes over this short video. State the order of entrances, occlusions, wipes, size changes and camera versus object motion only when actually visible. Separate observations from uncertainties. Do not invent unseen frames or quote lyrics.'},{'type':'video_url','video_url':{'url':'data:video/mp4;base64,'+base64.b64encode(p.read_bytes()).decode()}}]}],'reasoning_effort':'xhigh','chat_template_kwargs':{'enable_thinking':True},'stream':True,'stream_options':{'include_usage':True}}
  if variant['prompt']=='structured':payload['messages'][0]['content'][0]['text']=plan['structured_prompt']
  payload['mm_processor_kwargs']=plan['mm_processor_kwargs']
  payload['media_io_kwargs']={'video':{'num_frames':variant['num_frames']}}
  out.write_text(json.dumps({'state':'in_flight','variant':variant,'source':item,'started':time.time()}))
  print('START',variant['id'],p.name,'thinking=true effort=xhigh no request output cap',flush=True)
  req=urllib.request.Request('http://10.10.10.11:8000/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
  try:
   chunks=[];reasoning=[];content=[];usage=None;finish=None;meta={}
   with urllib.request.urlopen(req,timeout=3600) as res, out.with_suffix('.events.jsonl').open('w') as events:
    status=res.status
    for line in res:
     line=line.decode().strip()
     if not line.startswith('data: '):continue
     data=line[6:]
     if data=='[DONE]':break
     event=json.loads(data);events.write(json.dumps(event)+'\n');events.flush()
     if event.get('error'):raise RuntimeError('stream_error')
     for k in ['id','model','system_fingerprint']: 
      if event.get(k):meta[k]=event[k]
     if event.get('usage'):usage=event['usage']
     for choice in event.get('choices',[]):
      delta=choice.get('delta',{});r=delta.get('reasoning') or delta.get('reasoning_content') or '';c=delta.get('content') or ''
      if r:reasoning.append(r);print(r,end='',flush=True)
      if c:content.append(c);print(c,end='',flush=True)
      if choice.get('finish_reason'):finish=choice['finish_reason']
   response={**meta,'usage':usage,'choices':[{'message':{'role':'assistant','reasoning':''.join(reasoning),'content':''.join(content)},'finish_reason':finish}]}
   record={'state':'response_received_unreviewed' if finish else 'incomplete_stream','variant':variant,'source':item,'status':status,'response':response}

  except Exception as exc:record={'state':'failed','error_class':type(exc).__name__}
  out.write_text(json.dumps(record,indent=2));print('\nEND',variant['id'],p.name,record['state'],record.get('response',{}).get('usage'),flush=True)
  if record['state']=='failed':break
