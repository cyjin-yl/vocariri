import subprocess,json,os
from pathlib import Path
root=Path.cwd()
subprocess.run(['/opt/pv-tools/bin/python','ingest.py','queue-expansion-04-focused.json','--limit','16'],check=True)
for item in json.loads(Path('queue-expansion-04-focused.json').read_text()):
 source=root/'frames'/item['id'];dest=root/'materials'/item['id']
 if not (source/'manifest.json').exists():continue
 dest.mkdir(exist_ok=True)
 for p in source.glob('sheet-*.jpg'):
  target=dest/p.name
  if not target.exists():os.link(p,target)
print('Expansion acquisition checkpoint complete; starting direct-image analysis',flush=True)
subprocess.run(['/opt/pv-tools/bin/python','luna_visual_batches.py'],check=True)
