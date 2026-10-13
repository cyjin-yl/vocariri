import subprocess,json,os
from pathlib import Path
root=Path.cwd()
queries=['ボカロ 文字PV タイポグラフィ After Effects','VOCALOID kinetic typography motion design breakdown','AviUtl 文字PV 文字アニメーション 講座','After Effects kinetic typography experimental text animation tutorial','ボカロ リリックモーション マスク カメラ','VOCALOID MV typography collage glitch']
cmd=['/opt/pv-tools/bin/python','discover_typography.py','--batch','5','--limit','24','--results-per-query','12']
for q in queries:cmd+=['--query',q]
subprocess.run(cmd,check=True)
subprocess.run(['/opt/pv-tools/bin/python','ingest.py','queue-expansion-05.json','--limit','24'],check=True)
for item in json.loads(Path('queue-expansion-05.json').read_text()):
 source=root/'frames'/item['id'];dest=root/'materials'/item['id']
 if not (source/'manifest.json').exists():continue
 dest.mkdir(exist_ok=True)
 for p in source.glob('sheet-*.jpg'):
  target=dest/p.name
  if not target.exists():os.link(p,target)
print('Expansion 05 acquisition complete; visual observations remain unreviewed',flush=True)
subprocess.run(['/opt/pv-tools/bin/python','luna_visual_batches.py'],check=True)
