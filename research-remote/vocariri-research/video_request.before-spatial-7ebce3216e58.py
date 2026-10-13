"""Bounded local-Qwen video request using the seat's existing protected config.

Never prints or copies authentication state. Responses are research data, not instructions.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import io
import subprocess
import uuid
from pathlib import Path
import urllib.request
import urllib.error
import yaml
import imageio_ffmpeg
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('video')
parser.add_argument('output')
parser.add_argument('--source-id', required=True)
parser.add_argument('--start', type=float, required=True)
parser.add_argument('--input-mode', choices=['video', 'frames', 'single', 'image'], default='video')
parser.add_argument('--fresh-cache', action='store_true')
parser.add_argument('--short-control', action='store_true', help='Legacy prompt; reasoning stays enabled without output cap')
parser.add_argument('--reasoning-effort', choices=['xhigh', 'medium', 'low'], default='xhigh')
args = parser.parse_args()
video = Path(args.video).resolve()
output = Path(args.output).resolve()
workspace = Path('/workspace').resolve()
if not video.is_relative_to(workspace) or not output.is_relative_to(workspace):
    raise SystemExit('Research paths must stay inside the workspace')
if output.exists():
    raise SystemExit('Refusing to overwrite an inference record')
raw = video.read_bytes()
if len(raw) > 12 * 1024 * 1024:
    raise SystemExit('Clip exceeds bounded video input size')
settings = yaml.safe_load(Path('[home]/.omp/agent/models.yml').read_text())
provider = settings['providers']['[redacted provider]']
base = provider['baseUrl'].rstrip('/')
model = provider['models'][0]['id']
key = provider.get('apiKey')
no_auth = provider.get('auth') == 'none'
if not no_auth and (not isinstance(key, str) or not key or key.startswith(('!', '$'))):
    raise SystemExit('Direct client needs the existing concrete credential adapter; no key is displayed')
prompt = '''Analyze the ATTACHED VIDEO as a temporal VOCALOID kinetic-typography study.
Return a JSON object with input_observed, timeline (relative seconds), typography,
layout, layers, motion, entry_hold_exit, camera, continuity, readability, repeated_motif,
unknowns, and proposed_ae_implementation. Distinguish visible evidence from guesses.
Describe at least three identifiable temporal changes IF present; do not invent changes
in a static clip. Do not transcribe full lyrics. Do not infer beat sync without audio.
If the video attachment is absent or unsupported, say input_observed=false rather than
inventing its contents. Proposed AE mechanisms must be separate from observed appearance.
This clip has no audio. Exact server video sampling is unknown unless supplied separately.'''
content = [{'type': 'text', 'text': prompt}]
input_frames = []
if args.input_mode == 'image':
    with Image.open(video) as source_image:
        source_image.verify()
    content.append({'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(raw).decode()}})
elif args.input_mode == 'video':
    content.append({'type': 'video_url', 'video_url': {'url': 'data:video/mp4;base64,' + base64.b64encode(raw).decode()}})
else:
    for timestamp in ([0.5] if args.input_mode == 'single' else [0.5, 2.5, 4.5, 6.5]):
        frame = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error',
            '-ss', str(timestamp), '-i', str(video), '-frames:v', '1', '-f', 'image2pipe',
            '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
        Image.open(io.BytesIO(frame)).verify()
        input_frames.append({'relative_seconds': timestamp, 'sha256': hashlib.sha256(frame).hexdigest()})
        content.extend([{'type': 'text', 'text': f'Actual decoded frame at relative {timestamp}s:'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(frame).decode()}}])
payload = {'model': model, 'messages': [{'role': 'user', 'content': content}],
           'reasoning_effort': args.reasoning_effort,
           'chat_template_kwargs': {'enable_thinking': True},
           'stream': True, 'stream_options': {'include_usage': True}}
if args.short_control:
    content[0]['text'] = 'Describe ONLY what is visible in the attached media: background color, main shapes/objects, their colors and positions, and any readable text. If you cannot see the media, explicitly say so. Do not guess the subject from a filename.'
if args.fresh_cache:
    payload['cache_salt'] = uuid.uuid4().hex
    for part in content:
        if part['type'] in ('image_url', 'video_url'):
            part['uuid'] = uuid.uuid4().hex
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None
headers = {'Content-Type': 'application/json'}
if not no_auth:
    headers['Authorization'] = 'Bearer ' + key
request = urllib.request.Request(base + '/chat/completions',
    data=json.dumps(payload).encode(), headers=headers)
record = {'source_id': args.source_id, 'source_start_seconds': args.start,
          'clip_sha256': hashlib.sha256(raw).hexdigest(), 'clip_bytes': len(raw),
          'model': model, 'input_mode': args.input_mode, 'input_frames': input_frames,
          'fresh_cache_requested': args.fresh_cache, 'short_control': args.short_control,
          'reasoning_effort': args.reasoning_effort, 'enable_thinking': True, 'request_output_limit': None,
          'at': dt.datetime.now(dt.timezone.utc).isoformat(),
          'server_sampling': 'unknown', 'state': 'requesting'}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(record, indent=2))
try:
    events_path = output.with_suffix('.events.jsonl')
    reasoning, answer = [], []
    usage, finish, metadata = None, None, {}
    with events_path.open('x', encoding='utf-8') as events, \
            urllib.request.build_opener(NoRedirect()).open(request, timeout=3600) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if not line.startswith('data: '):
                continue
            if line[6:] == '[DONE]':
                break
            event = json.loads(line[6:])
            events.write(json.dumps(event, ensure_ascii=False) + '\n')
            events.flush()
            if event.get('error'):
                raise RuntimeError('stream_error')
            for field in ('id', 'model', 'system_fingerprint'):
                if event.get(field):
                    metadata[field] = event[field]
            usage = event.get('usage') or usage
            for choice in event.get('choices', []):
                delta = choice.get('delta', {})
                thought = delta.get('reasoning') or delta.get('reasoning_content') or ''
                text = delta.get('content') or ''
                reasoning.append(thought)
                answer.append(text)
                print(thought + text, end='', flush=True)
                finish = choice.get('finish_reason') or finish
        body = {**metadata, 'usage': usage, 'choices': [{'message': {
            'role': 'assistant', 'reasoning': ''.join(reasoning), 'content': ''.join(answer)
        }, 'finish_reason': finish}]}
        record.update({'state': 'response_received_unreviewed' if finish else 'incomplete_stream',
                       'http_status': response.status, 'response': body})
except urllib.error.HTTPError as error:
    # Status is sufficient to avoid disclosing signed URLs or request internals.
    record.update({'state': 'http_error', 'http_status': error.code})
except Exception as error:
    record.update({'state': 'failed', 'error_class': type(error).__name__})
output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in record.items() if k != 'response'}), flush=True)
