"""Exclusive import of independently reviewed native-cadence clip; no inference."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

root = Path('/workspace')
diag = root / 'r3atmp/codex-taildiag-20260927-7e2c'
clip_src = diag / 'remux.mp4'
receipt_src = diag / 'remux-recheck-test-receipt.json'
clip_dst = root / 'evidence/native/win-a-scale-native-r3c.mp4'
receipt_dst = root / 'evidence/native/win-a-scale-pts-r3c.json'
expected_clip = '810e39509b34646f2432164e843231671e3b34a6099398b8fa48fb3c30d32653'
expected_receipt = '7dc39807c9dbeac9c8c28a3fd56e9eaa0f26a386333119d013d1d90d6e2ba352'
expected_source = '9ab2c3cf22f64965ba76642c7fbb8d5fc8e760e51349d31692305a2f43ee84d7'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert digest(clip_src) == expected_clip
assert digest(receipt_src) == expected_receipt
assert digest(root / 'media/BV1zrbCzLEH4/source.mp4') == expected_source
assert not clip_dst.exists() and not receipt_dst.exists(), 'formal artifact already exists'
receipt = json.loads(receipt_src.read_text(encoding='utf-8'))
assert receipt['clip_sha256'] == expected_clip and receipt['source_sha256'] == expected_source
assert receipt['source_time_base'] == '1/16000' and len(receipt['source_pts']) == 18

for source, target, expected in ((clip_src, clip_dst, expected_clip),
                                 (receipt_src, receipt_dst, expected_receipt)):
    with source.open('rb') as inp, target.open('xb') as out:
        shutil.copyfileobj(inp, out)
    assert digest(target) == expected, ('post-copy hash mismatch', str(target))

module = root / 'checked-client-20260927/remote/video_request_checked.py'
client_sha = digest(module)
assert client_sha == 'b93661cd6573ab1e5a95cfd7e83544b6379e23d2dec9192691618b2d89de952b'
sys.path.insert(0, str(module.parent))
from video_request_checked import probe_video, validate_native_receipt
probe = probe_video(clip_dst)
checked = validate_native_receipt(receipt_dst, root, expected_clip, probe)
assert probe['decoded_frames'] == 18 and probe['time_base'] == '1/16000'
assert probe['pts'] == [0,528,1072,1600,2128,2672,3200,3744,4272,4800,5344,
                        5872,6400,6944,7472,8000,8544,9072]
assert checked['receipt_sha256'] == expected_receipt
print(json.dumps({'result':'formal_transport_pass','clip_sha256':expected_clip,
                  'receipt_sha256':expected_receipt,'client_sha256':client_sha,
                  'decoded_frames':probe['decoded_frames'],'pts':probe['pts']}))
