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
 p={'model':'[redacted model]','messages':[{'role':'user','content':([{'type':'text','text':prefix}] if prefix else [])+content}],'temperature':0,'max_tokens':260,'chat_template_kwargs':{'enable_thinking':False}}
 if salt:p['cache_salt']=uuid.uuid4().hex
 target.write_text(json.dumps({'state':'in_flight','started':time.time()}));t=time.monotonic()
 req=urllib.request.Request('http://10.10.10.11:8000/v1/chat/completions',data=json.dumps(p).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
 try:
  with urllib.request.urlopen(req,timeout=240) as r: result={'status':r.status,'response':json.load(r),'elapsed':time.monotonic()-t}
 except urllib.error.HTTPError as e:result={'status':e.code}
 except Exception as e:result={'error_class':type(e).__name__}
 target.write_text(json.dumps(result,indent=2));print(name,json.dumps(result),flush=True)
def image_content(i):return [{'type':'text','text':'Describe the shapes, colors, positions and text visible in this image. Be concise.'},{'type':'image_url','image_url':{'url':images[i]}}]

h264='data:video/mp4;base64,'+base64.b64encode((root/'sequence-h264.mp4').read_bytes()).decode()
call('v2-video-h264',[{'type':'text','text':'List each distinct scene in chronological order, with its shapes, colors and exact printed label. Use one short line per scene.'},{'type':'video_url','video_url':{'url':h264}}])
for i in [1,3,0,2]:call('v2-after-h264-'+str(i),image_content(i),salt=False)
