import base64,json,time,urllib.request,urllib.error,shlex,hashlib
from pathlib import Path
root=Path(__file__).parent/'prompt-ab'
plan=json.loads((root/'plan.json').read_text())
clips=Path('/tank/shared/projects/vocariri-research/luna-public/outputs/qwen-control-05')
key=next(shlex.split(x.split('=',1)[1])[0] for x in Path('/etc/1cat-vllm.env').read_text().splitlines() if x.startswith('VLLM_API_KEY='))
for variant in plan['variants']:
 for item in json.loads((clips/'clips.json').read_text()):
  p=clips/item['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
  out=root/(variant['id']+'-'+p.stem+'.json')
  if out.exists():continue
  payload={'model':'[redacted model]','messages':[{'role':'user','content':[{'type':'text','text':'Describe the visible typography and its changes over this short video. State the order of entrances, occlusions, wipes, size changes and camera versus object motion only when actually visible. Separate observations from uncertainties. Do not invent unseen frames or quote lyrics. Be concise.'},{'type':'video_url','video_url':{'url':'data:video/mp4;base64,'+base64.b64encode(p.read_bytes()).decode()}}]}],'temperature':0,'max_tokens':650,'chat_template_kwargs':{'enable_thinking':False}}
  if variant['prompt']=='structured':payload['messages'][0]['content'][0]['text']=plan['structured_prompt']
  payload['media_io_kwargs']={'video':{'num_frames':variant['num_frames']}}
  out.write_text(json.dumps({'state':'in_flight','variant':variant,'source':item,'started':time.time()}))
  req=urllib.request.Request('http://10.10.10.11:8000/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
  try:
   with urllib.request.urlopen(req,timeout=180) as res:record={'state':'response_received_unreviewed','variant':variant,'source':item,'status':res.status,'response':json.load(res)}
  except Exception as exc:record={'state':'failed','error_class':type(exc).__name__}
  out.write_text(json.dumps(record,indent=2));print(p.name,json.dumps(record),flush=True)
  if record['state']=='failed':break
