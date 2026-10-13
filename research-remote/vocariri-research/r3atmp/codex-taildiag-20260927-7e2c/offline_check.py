"""Offline checked-client verification of the remux candidate; sends no request."""
from pathlib import Path
import hashlib, json, sys
root = Path('/workspace')
module = root/'checked-client-20260927/remote/video_request_checked.py'
client_sha = hashlib.sha256(module.read_bytes()).hexdigest()
assert client_sha == 'b93661cd6573ab1e5a95cfd7e83544b6379e23d2dec9192691618b2d89de952b'
sys.path.insert(0, str(module.parent))
from video_request_checked import probe_video, validate_native_receipt
clip = root/'r3atmp/codex-taildiag-20260927-7e2c/remux.mp4'
receipt = root/'r3atmp/codex-taildiag-20260927-7e2c/remux-recheck-test-receipt.json'
clip_sha = hashlib.sha256(clip.read_bytes()).hexdigest()
assert clip_sha == '810e39509b34646f2432164e843231671e3b34a6099398b8fa48fb3c30d32653'
probe = probe_video(clip)
checked = validate_native_receipt(receipt, root, clip_sha, probe)
assert probe['decoded_frames'] == 18 and probe['time_base'] == '1/16000'
assert probe['pts'] == [0,528,1072,1600,2128,2672,3200,3744,4272,4800,5344,5872,6400,6944,7472,8000,8544,9072]
print(json.dumps({'clip_sha256':clip_sha,'decoded_frames':probe['decoded_frames'],
 'time_base':probe['time_base'],'pts':probe['pts'],'duration_seconds':probe['duration_seconds'],
 'receipt_sha256':checked['receipt_sha256'],'client_module_sha256':client_sha}))
