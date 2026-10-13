import json,time,shlex,urllib.request,subprocess,hashlib
from pathlib import Path
root=Path('/tmp/vocariri-video-check')
source=Path('/tank/shared/projects/1Cat-vLLM/scripts/vm101-serve.sh')
raw=source.read_text();assert raw.count('export VLLM_USE_V2_MODEL_RUNNER=1')==1
trial=root/'multimodal-maintenance-20260924/serve-v1.sh';trial.write_text(raw.replace('export VLLM_USE_V2_MODEL_RUNNER=1','export VLLM_USE_V2_MODEL_RUNNER=0'))
key=next(shlex.split(x.split('=',1)[1])[0] for x in Path('/etc/1cat-vllm.env').read_text().splitlines() if x.startswith('VLLM_API_KEY='))
def get(path):
 req=urllib.request.Request('http://10.10.10.11:8000'+path,headers={'Authorization':'Bearer '+key})
 return urllib.request.urlopen(req,timeout=5).read().decode()
def idle():
 s=get('/metrics');v=[float(l.rsplit(' ',1)[1]) for l in s.splitlines() if l.startswith(('vllm:num_requests_running{','vllm:num_requests_waiting{'))];return len(v)>=2 and all(x==0 for x in v)
record=root/'multimodal-maintenance-20260924/state.json'
def save(state):
 record.write_text(json.dumps({'state':state,'time':time.time(),'original_sha256':hashlib.sha256(raw.encode()).hexdigest()}));print(state,flush=True)
try:
 get('/health')
 if not idle(): raise SystemExit('Live service busy; abort')
except urllib.error.URLError: pass
save('starting_authorized_multimodal_trial')
unit=Path('/run/systemd/system/vm101-swift-qwen.service.d/90-vocariri-runner-ab.conf');unit.parent.mkdir(parents=True,exist_ok=True)
assert not unit.exists()
unit.write_text('[Service]\nExecStart=\nExecStart=/bin/bash '+str(trial)+'\nTimeoutStopSec=infinity\nSendSIGKILL=no\n')
subprocess.run(['systemctl','daemon-reload'],check=True);save('restarting_v1')
subprocess.run(['systemctl','restart','vm101-swift-qwen.service'],check=True)
end=time.monotonic()+600
while time.monotonic()<end:
 try:
  get('/health');save('v1_ready');raise SystemExit(0)
 except urllib.error.URLError:pass
 if subprocess.run(['systemctl','is-failed','--quiet','vm101-swift-qwen.service']).returncode==0:break
 time.sleep(5)
unit.unlink();subprocess.run(['systemctl','daemon-reload'],check=True);save('restoring_original_after_trial_start_failure');subprocess.run(['systemctl','restart','vm101-swift-qwen.service'],check=True);save('original_restart_requested')
