import base64,io,json,uuid,urllib.request,urllib.error,shlex,time,concurrent.futures
from pathlib import Path
from PIL import Image,ImageDraw
import cv2,numpy as np
root=Path(__file__).parent
key=next(shlex.split(x.split('=',1)[1])[0] for x in Path('/etc/1cat-vllm.env').read_text().splitlines() if x.startswith('VLLM_API_KEY='))
def make(i):
 im=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(im)
 if i==0:d.rectangle((30,60,210,240),fill='red');d.ellipse((300,60,480,240),fill='blue')
 elif i==1:d.polygon([(100,50),(20,230),(180,230)],fill='green');d.rectangle((300,60,480,240),fill='orange')
 elif i==2:d.ellipse((30,60,210,240),fill='purple');d.polygon([(380,40),(470,230),(280,230)],fill='black')
 else:d.rectangle((30,60,210,240),fill='blue');d.ellipse((300,60,480,240),fill='red')
 label=['PV731','ZX482','LM596','AB204'][i];d.text((180,300),label,fill='black',font_size=48)
 return im
images=[]
for i in range(4):
 im=make(i);im.save(root/f'control-{i}.png');b=io.BytesIO();im.save(b,format='PNG');images.append('data:image/png;base64,'+base64.b64encode(b.getvalue()).decode())
video=root/'sequence-mp4v.mp4'
w=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),4,(512,384));assert w.isOpened()
for i in range(4):
 for _ in range(8):w.write(cv2.cvtColor(np.array(make(i)),cv2.COLOR_RGB2BGR))
w.release()
video_url='data:video/mp4;base64,'+base64.b64encode(video.read_bytes()).decode()
def call(name,content,prefix='',salt=True):
 target=root/(name+'.json');assert not target.exists()
 p={'model':'[redacted model]','messages':[{'role':'user','content':([{'type':'text','text':prefix}] if prefix else [])+content}],'temperature':0,'max_tokens':600,'chat_template_kwargs':{'enable_thinking':False}}
 if salt:p['cache_salt']=uuid.uuid4().hex
 target.write_text(json.dumps({'state':'in_flight','started':time.time()}));t=time.monotonic()
 req=urllib.request.Request('http://10.10.10.11:8000/v1/chat/completions',data=json.dumps(p).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
 try:
  with urllib.request.urlopen(req,timeout=240) as r: result={'status':r.status,'response':json.load(r),'elapsed':time.monotonic()-t}
 except urllib.error.HTTPError as e:result={'status':e.code}
 except Exception as e:result={'error_class':type(e).__name__}
 target.write_text(json.dumps(result,indent=2));print(name,json.dumps(result),flush=True)
def image_content(i):return [{'type':'text','text':'Describe the shapes, colors, positions and text visible in this image. Be concise.'},{'type':'image_url','image_url':{'url':images[i]}}]

import threading
observations=[];stop=threading.Event();barrier=threading.Barrier(4)
def metrics():
 while not stop.is_set():
  try:
   req=urllib.request.Request('http://10.10.10.11:8000/metrics',headers={'Authorization':'Bearer '+key})
   with urllib.request.urlopen(req,timeout=3) as r:raw=r.read().decode()
   vals={l.split('{')[0]:float(l.rsplit(' ',1)[1]) for l in raw.splitlines() if l.startswith(('vllm:num_requests_running{','vllm:num_requests_waiting{','vllm:spec_decode_num_drafts_total{','vllm:spec_decode_num_accepted_tokens_total{'))}
   observations.append({'time':time.time(),**vals})
  except Exception as e:observations.append({'time':time.time(),'error_class':type(e).__name__})
  stop.wait(.15)
t=threading.Thread(target=metrics);t.start()
prefix='The following is irrelevant filler. Describe only the attached image. '+('neutral context padding words. '*1900)
def job(i):
 barrier.wait()
 content=image_content(i);content[0]['text']='Describe the shapes, colors, text, placement and geometric features in detail. Do not discuss the filler.'
 call('v2-long-concurrent-'+str(i),content,prefix=prefix,salt=False)
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(job,range(4)))
 call('v2-video-complete',[{'type':'text','text':'List each distinct scene in chronological order, with its shapes, colors and exact printed label. Use one short line per scene.'},{'type':'video_url','video_url':{'url':video_url}}])
 for i in [3,0,2,1]:call('v2-cache-reuse-'+str(i),image_content(i),prefix=prefix,salt=False)
finally:
 stop.set();t.join();(root/'v2-concurrency-metrics.json').write_text(json.dumps(observations,indent=2))
print('STRESS_COMPLETE',flush=True)
