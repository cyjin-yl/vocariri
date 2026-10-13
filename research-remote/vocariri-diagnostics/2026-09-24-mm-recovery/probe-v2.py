import base64, io, json, uuid, urllib.request, urllib.error, shlex
from pathlib import Path
from PIL import Image, ImageDraw
out=Path('/tmp/vocariri-video-check/multimodal-maintenance-20260924/v2-baseline-image.json')
if out.exists(): raise SystemExit('Existing record; inspect first')
im=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(im);d.rectangle((30,60,210,240),fill='red');d.ellipse((300,60,480,240),fill='blue');d.text((180,300),'PV731',fill='black',font_size=48)
b=io.BytesIO();im.save(b,format='PNG')
p={'model':'[redacted model]','messages':[{'role':'user','content':[{'type':'text','text':'Describe the shapes, colors and text visible in this image.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()}}]}],'temperature':0,'max_tokens':200,'chat_template_kwargs':{'enable_thinking':False},'cache_salt':uuid.uuid4().hex}
e={}
for line in Path('/etc/1cat-vllm.env').read_text().splitlines():
 if line.startswith('VLLM_API_KEY='):e['key']=shlex.split(line.split('=',1)[1])[0]
req=urllib.request.Request('http://10.10.10.11:8000/v1/chat/completions',data=json.dumps(p).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+e['key']})
out.write_text(json.dumps({'state':'requesting'}))
try:
 with urllib.request.urlopen(req,timeout=180) as r: result={'status':r.status,'response':json.load(r)}
except urllib.error.HTTPError as e:result={'status':e.code}
except Exception as e:result={'error_class':type(e).__name__}
out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
