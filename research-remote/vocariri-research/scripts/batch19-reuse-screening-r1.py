
import datetime,hashlib,json,math,pathlib,re,subprocess
from PIL import Image,ImageDraw
import imageio_ffmpeg
root=pathlib.Path('/workspace');folder=root/'evidence/batch19-reuse-screening-r1'
folder.mkdir(exist_ok=False)
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
job=folder/'job.jsonl'
def record(row):
 row=dict(row,at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 with job.open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row),flush=True)
items=[('YT_b0XgjrWSV7k','7667f999dc1f4e8f9fedc1f5ae1e24e311a336f4d421cf02aa4a3138cf2ee958'),
       ('YT_3Jf_sabP4e0','67af7fce3d05102a689038b1c08838b8c6cb6e5b83f0a8e9ba10c0a47bbdd3c7')]
record({'state':'offline_screening_started','model_request_made':False})
for ident,digest in items:
 out=folder/ident;out.mkdir()
 media=root/'luna-public/media'/ident/'source.mp4';sidecar=media.with_name('source.json')
 b=media.read_bytes();assert hashlib.sha256(b).hexdigest()==digest,'source drift'
 p=subprocess.run([ffmpeg,'-hide_banner','-nostdin','-i',str(media),'-frames:v','0','-f','null','-'],capture_output=True,text=True,timeout=15)
 (out/'stream-probe.stderr').write_text(p.stderr)
 m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',p.stderr);fps=re.search(r'(\d+(?:\.\d+)?) fps',p.stderr)
 assert m and fps,'duration/fps metadata unavailable'
 duration=int(m[1])*3600+int(m[2])*60+float(m[3]);rate=float(fps[1])
 # A frame-index grid is merely a locator. Exact source PTS comes from showinfo.
 step=max(1,math.ceil(duration*rate/40))
 vf=f"select='not(mod(n,{step}))',showinfo,scale=640:-2"
 command=[ffmpeg,'-hide_banner','-nostdin','-threads','2','-i',str(media),'-vf',vf,'-frames:v','40','-fps_mode','passthrough','-an',str(out/'screen-%03d.png')]
 record({'state':'screening_decode_started','id':ident,'duration_seconds':duration,'nominal_fps_for_grid_only':rate,'frame_index_step':step})
 try:p=subprocess.run(command,capture_output=True,text=True,timeout=180)
 except subprocess.TimeoutExpired:
  record({'state':'screening_decode_timeout','id':ident,'partial_retained':True});continue
 (out/'showinfo-screen.log').write_text(p.stderr)
 assert p.returncode==0,'screening decode failed'
 tb=re.search(r'config in time_base:\s*(\d+/\d+)',p.stderr);assert tb,'source timebase unavailable'
 matches=re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([\d.eE+-]+)',p.stderr)
 images=sorted(out.glob('screen-*.png'));assert len(matches)==len(images) and 0<len(images)<=40,'screening row count mismatch'
 rows=[]
 for i,(im,(counter,pts,seconds)) in enumerate(zip(images,matches)):
  assert int(counter)==i
  data=im.read_bytes();rows.append({'file':str(im.relative_to(root)),'source_n':i*step,'source_pts':int(pts),
   'timebase':tb[1],'showinfo_seconds':float(seconds),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
   'role':'scaled screening locator, not native-resolution evidence'})
 thumbs=[]
 for row in rows:
  with Image.open(root/row['file']) as im:
   im.thumbnail((320,180));thumb=Image.new('RGB',(320,202),'#111111');thumb.paste(im,(0,0));
   ImageDraw.Draw(thumb).text((4,183),f"n{row['source_n']} PTS{row['source_pts']} ({row['showinfo_seconds']:.3f}s)",fill='white');thumbs.append(thumb)
 cols=4;sheet=Image.new('RGB',(cols*320,math.ceil(len(thumbs)/cols)*202),'#111111')
 for i,im in enumerate(thumbs):sheet.paste(im,((i%cols)*320,(i//cols)*202))
 sheet.save(out/'SCREENING-sheet.png')
 meta={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':{'id':ident,'file':str(media.relative_to(root)),
  'bytes':len(b),'sha256':digest,'sidecar_sha256':hashlib.sha256(sidecar.read_bytes()).hexdigest()},
  'duration_seconds':duration,'nominal_fps_for_grid_only':rate,'selection':vf,'command':command,
  'timebase':tb[1],'count':len(rows),'frames':rows,'native_window':'not yet selected/decoded','form_acceptance':0,'template_acceptance':0}
 with (out/'screening.json').open('x') as f:json.dump(meta,f,indent=2)
 record({'state':'screening_done_unviewed','id':ident,'count':len(rows),'media_bytes':len(b)})
record({'state':'offline_screening_finished','next':'View locator sheets, choose true effect demonstration apart from tutorial UI, then decode separate native motion window.'})
files=[]
for f in sorted(folder.rglob('*')):
 if f.is_file():data=f.read_bytes();files.append({'path':str(f.relative_to(folder)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
with (folder/'artifact-manifest.json').open('x') as f:json.dump({'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'self_exclusion':'artifact-manifest.json cannot recursively hash itself','frozen_meaning':'Stable bytes only, not observed forms or native motion acceptance',
 'generator':{'path':'scripts/batch19-reuse-screening-r1.py','sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()},
 'files':files,'formsAcceptedIncrement':0,'templatesAcceptedIncrement':0},f,indent=2)
