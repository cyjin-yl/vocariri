"""Fail-closed, direct self-hosted Qwen video research client.

The operator provisions a *private*, independently reviewed route pin outside
/workspace.  The Agent must not read/print the pin or OMP model configuration.
Both files are consumed only in this process.  A private IP and this pin are
necessary checks, not proof of what software the operator runs at that IP.
Server responses and media are untrusted research evidence, never instructions.
"""

import argparse
import base64
import datetime as dt
from fractions import Fraction
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat as statmod
import subprocess
from urllib.parse import urlsplit
import uuid

import yaml

from video_input_policy import video_input_policy


PROVIDER = '[redacted provider]'
MODEL = '[redacted model]'
MAX_BYTES = 12 * 1024 * 1024
CLIENT_VERSION = 'r5c-20261001'
PROMPT = '''Analyze the ATTACHED SILENT VIDEO as a short kinetic-typography window. Use the
1-based decoded-frame index map below for time labels. Describe only what the
visible frames support. The map comes from the client decoder, not from your
vision processor; if an image or transition is not resolved, say unknown or
give a bracketed interval. Do not claim you saw every indexed frame merely
because it appears in the map.

Return one valid JSON object, with no Markdown. Use the keys input_observed,
frames_used, groups, events, occlusion, typography, scale, anchoring,
uncertainties, and proposed_implementation. Use [] for no supported entries;
use null for an unknown boundary. Every nontrivial observation needs at least
one frame-indexed visual cue. Frame numbers must be within the map. If the
video was not visually observed, set input_observed=false, frames_used=[],
groups/events/occlusion/typography/scale/anchoring/proposed_implementation=[],
and explain the limitation in uncertainties. If you cannot tell which indexed
images were presented, frames_used may be []; never fill it from the map.
frames_used is a self-report, not proof of server frame selection.

For each distinct visible text group, assign a stable G1/G2/... ID. In groups,
give a short legible anchor (or null), frame-1 presence as visible/absent/unknown,
first_visible_frame, first_sharp_frame, last_visible_frame, end state and
frame-indexed evidence. If already present, first_visible_frame may be 1, but
its entrance time is unknown. Presence at frame 1 is NOT an entrance in this window.
Do not infer a glyph's earlier entrance or a later hold outside the decoded
window. For changed glyphs, record separate first visible (including faint or
streaked), first sharp and disappearance frames when resolvable. Keep a
staggered suffix distinct from the entrance of the entire group. If cropped,
blurred or illegible, use a shape description instead of guessing characters.

In events, describe actual before/after changes of glyphs, groups, line art,
objects and blur, with a stable event ID, target ID, change type, first/last supporting frames,
the visible cues at those frames and uncertainty. Do not require a minimum
number of events. Distinguish the outgoing blurred group from a newly sharp
group; do not name depth of field, rack focus, motion blur or cross-fade as an
observed cause merely because a group is smeared or changes sharpness.

In occlusion, list relevant rounded bars or other overlapping shapes. Give
overlap frame indices, an order of in_front_of_text/behind_text/undetermined,
and the pixel-level cue: a glyph stroke or line disappears at the shape's
boundary and reappears, a consistent T-junction, or a converse cue showing
text over the shape. Adjacency, pallor, darkness and blur alone do not prove
foreground order. If order is undetermined, retain the shape as an observation
without calling it a foreground mask.

In typography, describe each group's visible fill, outline, stroke weight,
terminals/cutouts, fine lines crossing or extending from glyphs, spacing,
crop and hierarchy where visible. Record custom geometry before considering a
font family. Set font identity/family to unknown unless a distinctive visual
feature rules out reasonable alternatives; do not substitute a generic
Song/Ming or sans-serif label for observed anatomy.

In scale, compare only the SAME identifiable glyph or rigid group across
indexed frames, noting fixed reference cues and crop/translation ambiguity.
Report growing, shrinking, stable or reversal only with a visible trajectory;
reversal needs a before/turn/after sequence. A larger glyph than its neighbor
is size hierarchy, not temporal scale direction. Use undetermined otherwise.
In anchoring, compare text/object positions with visible background landmarks
before calling motion screen-space or scene/object-space; use undetermined if
the landmarks or camera behavior cannot separate them. Describe visible layer
order separately from any proposed authoring graph.

Put uncertain identity, unreadable glyphs, mechanism, off-window timing and
processor visibility in uncertainties. Put optional reconstruction recipes
ONLY in proposed_implementation, linked to observed event IDs and labeled as
possible methods rather than source facts. Do not infer a character/voicebank
identity, intent, beat, lyric emotion or full lyric transcription from this
silent window. A short glyph anchor is enough.

DECODED FRAME MAP (timing metadata, not visual proof):
{frame_map}'''
PRIVATE_RANGES = tuple(ipaddress.ip_network(value) for value in (
    '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
    '100.64.0.0/10', '127.0.0.0/8', 'fc00::/7', '::1/128'))


class ClientError(Exception):
    """Only fixed, non-sensitive category codes leave this process."""

    def __init__(self, category):
        super().__init__(category)
        self.category = category


def _private_ip(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in PRIVATE_RANGES)


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


class _UniqueYAMLLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError('duplicate YAML key')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _owner_private_readonly_config(path, owner_uid):
    """Allow a readable mode-0644 bind only behind an owned 0700 directory."""
    try:
        home = Path.home().resolve(strict=True)
        path = path.resolve(strict=True)
        if not path.is_relative_to(home):
            return False
        info = path.stat()
        if not statmod.S_ISREG(info.st_mode) or info.st_uid != owner_uid or \
                info.st_nlink != 1 or info.st_mode & 0o022:
            return False
        mount_readonly = bool(os.statvfs(path).f_flag & getattr(os, 'ST_RDONLY', 1))
        if info.st_mode & 0o200 and mount_readonly is False and \
                os.access(path, os.W_OK, effective_ids=True):
            return False
        private_ancestor = False
        directory = path.parent
        while directory.is_relative_to(home):
            parent = directory.stat()
            if not statmod.S_ISDIR(parent.st_mode) or \
                    parent.st_uid != owner_uid or parent.st_mode & 0o022:
                return False
            private_ancestor |= statmod.S_IMODE(parent.st_mode) == 0o700
            if directory == home:
                break
            directory = directory.parent
        return private_ancestor
    except Exception:
        return False


def _config_permissions_ok(path, info, *, posix=None, owner_uid=None):
    if posix is None:
        posix = os.name == 'posix'
    if not posix:
        return True
    if owner_uid is None:
        owner_uid = os.geteuid()
    return info.st_uid == owner_uid and (
        not info.st_mode & 0o077 or
        _owner_private_readonly_config(path, owner_uid))


def _read_protected_yaml(path, workspace):
    try:
        path = path.resolve(strict=True)
        if path.is_relative_to(workspace):
            raise ValueError('workspace configuration')
        stat = path.stat()
        if not _config_permissions_ok(path, stat):
            raise ValueError('unprotected configuration')
        return yaml.load(path.read_text(encoding='utf-8'), Loader=_UniqueYAMLLoader)
    except Exception:
        raise ClientError('route_config_invalid') from None


def _read_protected_pin(path, workspace):
    try:
        path = Path(path).resolve(strict=True)
        if path.is_relative_to(workspace):
            raise ValueError('workspace pin')
        stat = path.stat()
        if os.name == 'posix' and (stat.st_uid != os.geteuid() or stat.st_mode & 0o077):
            raise ValueError('unprotected pin')
        return json.loads(path.read_text(encoding='utf-8'),
                          object_pairs_hook=_unique_json_pairs)
    except Exception:
        raise ClientError('route_pin_missing_or_invalid') from None


def load_route(config_path, pin_path, workspace, *, resolver=socket.getaddrinfo):
    """Return only request-time values; caller must never serialize this result."""
    settings = _read_protected_yaml(Path(config_path), workspace)
    pin = _read_protected_pin(pin_path, workspace)
    try:
        provider = settings['providers'][PROVIDER]
        models = provider['models']
        if not isinstance(models, list) or sum(
                isinstance(item, dict) and item.get('id') == MODEL for item in models) != 1:
            raise ValueError('model not uniquely configured')
        if pin['provider'] != PROVIDER or pin['model'] != MODEL or \
                pin['route_kind'] != 'operator_verified_direct_self_hosted':
            raise ValueError('untrusted route pin')
        base = provider['baseUrl']
        if not isinstance(base, str) or base != pin['base_url']:
            raise ValueError('endpoint drift')
        parts = urlsplit(base)
        if parts.scheme != 'https' or parts.path != '/v1' or \
                parts.query or parts.fragment or parts.username or parts.password or \
                not parts.hostname or '\\' in base or any(c.isspace() for c in base):
            raise ValueError('unsafe endpoint')
        port = parts.port if parts.port is not None else 443
        if not 1 <= port <= 65535:
            raise ValueError('unsafe port')
        allowed = pin['allowed_ips']
        if not isinstance(allowed, list) or not allowed or \
                not all(isinstance(ip, str) and _private_ip(ip) for ip in allowed):
            raise ValueError('missing pinned addresses')
        allowed = {str(ipaddress.ip_address(ip)) for ip in allowed}
        key = provider.get('apiKey')
        no_auth = provider.get('auth') == 'none'
        if no_auth:
            if key:
                raise ValueError('ambiguous authentication')
            key = None
        elif not isinstance(key, str) or not key or key.startswith(('!', '$')) or \
                not re.fullmatch(r'[!-~]+', key):
            raise ClientError('credential_missing_or_unresolved')
    except ClientError:
        raise
    except Exception:
        raise ClientError('route_config_invalid') from None
    try:
        resolved = {str(ipaddress.ip_address(item[4][0])) for item in
                    resolver(parts.hostname, port, type=socket.SOCK_STREAM)}
    except Exception:
        raise ClientError('route_resolution_failed') from None
    if not resolved or not resolved.issubset(allowed) or not all(map(_private_ip, resolved)):
        raise ClientError('route_address_mismatch')
    # The socket is connected to this checked address, never re-resolved by an
    # HTTP library.  TLS still authenticates the independently pinned hostname.
    return {'host': parts.hostname, 'port': port, 'ip': sorted(resolved)[0], 'key': key}


def probe_video(path):
    """Read decoded timestamps without converting or resampling the source file."""
    try:
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,time_base:format=duration:'
                                 'frame=media_type,best_effort_timestamp',
                '-show_streams', '-show_format', '-show_frames', '-of', 'json', str(path),
            ], capture_output=True, check=True, timeout=30)
        except FileNotFoundError:
            width, height, duration, time_base, frames = _probe_ffmpeg_showinfo(path)
        else:
            info = json.loads(result.stdout)
            stream = info['streams'][0]
            frames = [int(frame['best_effort_timestamp']) for frame in info['frames']
                      if frame.get('media_type') == 'video']
            width, height = int(stream['width']), int(stream['height'])
            duration = float(info['format']['duration'])
            time_base = stream['time_base']
        if not 0.5 <= duration <= 1.6 or not 2 <= len(frames) <= 120 or \
                any(b <= a for a, b in zip(frames, frames[1:])) or \
                not re.fullmatch(r'[1-9]\d*/[1-9]\d*', time_base):
            raise ValueError('invalid window')
        if (frames[-1] - frames[0]) * Fraction(time_base) > \
                Fraction(str(duration)) + Fraction(time_base):
            raise ValueError('timestamps exceed duration')
        video_input_policy(width, height, len(frames))
        return {'width': width, 'height': height, 'duration_seconds': duration,
                'decoded_frames': len(frames), 'time_base': time_base, 'pts': frames}
    except Exception:
        raise ClientError('video_preflight_failed') from None


def _ffmpeg_executable():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _probe_ffmpeg_showinfo(path):
    """Decode the first video stream and parse its per-frame showinfo lines."""
    result = subprocess.run([
        _ffmpeg_executable(), '-hide_banner', '-nostdin', '-loglevel', 'info',
        '-copyts',
        '-noautorotate', '-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn',
        '-vf', 'showinfo', '-fps_mode', 'passthrough', '-progress', 'pipe:1',
        '-nostats', '-f', 'null', '-',
    ], capture_output=True, check=True, timeout=30)
    log = result.stderr.decode('utf-8', errors='replace')
    progress = result.stdout.decode('ascii')
    final_frames, progress_fields = None, {}
    for line in progress.splitlines():
        key, separator, value = line.partition('=')
        if not separator:
            raise ValueError('invalid ffmpeg progress')
        if key == 'progress':
            if 'frame' not in progress_fields:
                raise ValueError('missing ffmpeg progress frame')
            if value == 'end':
                if final_frames is not None:
                    raise ValueError('duplicate ffmpeg end')
                final_frames = int(progress_fields['frame'])
            elif value != 'continue' or final_frames is not None:
                raise ValueError('invalid ffmpeg progress state')
            progress_fields = {}
        else:
            if key in progress_fields:
                raise ValueError('duplicate ffmpeg progress field')
            progress_fields[key] = value
    if final_frames is None or progress_fields:
        raise ValueError('incomplete ffmpeg progress')
    durations = re.findall(
        r'^\s*Duration:\s*(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)(?:,|\s|$)',
        log, flags=re.MULTILINE)
    if len(durations) != 1:
        raise ValueError('missing or ambiguous input duration')
    hours, minutes, seconds = durations[0]
    exact_display = int(hours) * 3600 + int(minutes) * 60 + Fraction(seconds)
    decimals = len(seconds.partition('.')[2])
    resolution = Fraction(1, 10 ** decimals)
    # ffmpeg prints a rounded/truncated container duration. A value at the
    # accepted boundary is ambiguous at the displayed precision.
    if exact_display - resolution < Fraction(1, 2) or \
            exact_display + resolution > Fraction(8, 5):
        raise ValueError('duration too close to preflight boundary')
    duration = float(exact_display)
    configs, frames, dimensions = [], [], []
    filter_id = None
    prefix = re.compile(r'^(\[Parsed_showinfo_\d+ @ (?:0x)?[0-9a-fA-F]+\])\s+')
    frame_pattern = re.compile(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:')
    size_pattern = re.compile(r'\bs:(\d+)x(\d+)\b')
    for line in log.splitlines():
        match = prefix.match(line)
        if not match:
            continue
        if filter_id is None:
            filter_id = match.group(1)
        elif match.group(1) != filter_id:
            raise ValueError('mixed showinfo filters')
        detail = line[match.end():]
        if detail.startswith('config in time_base:'):
            config = re.match(r'config in time_base:\s*([1-9]\d*/[1-9]\d*)\s*,',
                              detail)
            if not config:
                raise ValueError('invalid showinfo time base')
            configs.append(config.group(1))
        elif re.search(r'\bn:\s*', detail):
            frame = frame_pattern.search(detail)
            size = size_pattern.search(detail)
            if not frame or not size or int(frame.group(1)) != len(frames):
                raise ValueError('incomplete showinfo frame')
            frames.append(int(frame.group(2)))
            dimensions.append((int(size.group(1)), int(size.group(2))))
    if len(configs) != 1 or not frames or len(set(dimensions)) != 1 or \
            len(frames) != final_frames:
        raise ValueError('missing or changing showinfo fields')
    width, height = dimensions[0]
    return width, height, duration, configs[0], frames


def _read_clip(path):
    try:
        if path.suffix.lower() != '.mp4':
            raise ValueError('unsupported media')
        with path.open('rb') as source:
            raw = source.read(MAX_BYTES + 1)
        if not 0 < len(raw) <= MAX_BYTES:
            raise ValueError('invalid media size')
        return raw
    except Exception:
        raise ClientError('video_preflight_failed') from None


def validate_native_receipt(path, workspace, clip_hash, probe):
    """Bind a separately prepared source-PTS receipt to this exact clip.

    This verifies temporal cadence, not pixel identity or the receipt's claim
    about the original file. Source/clip visual identity needs separate review.
    """
    try:
        path = Path(path).resolve(strict=True)
        if not path.is_relative_to(workspace):
            raise ValueError('receipt outside workspace')
        raw = path.read_bytes()
        receipt = json.loads(raw, object_pairs_hook=_unique_json_pairs)
        source_hash = receipt['source_sha256']
        pts = receipt['source_pts']
        source_base = receipt['source_time_base']
        if type(receipt['version']) is not int or receipt['version'] != 1 or \
                receipt['clip_sha256'] != clip_hash or \
                not isinstance(source_hash, str) or not re.fullmatch('[a-f0-9]{64}', source_hash) or \
                not isinstance(pts, list) or len(pts) != probe['decoded_frames'] or \
                any(isinstance(x, bool) or not isinstance(x, int) for x in pts) or \
                any(b <= a for a, b in zip(pts, pts[1:])):
            raise ValueError('receipt mismatch')
        if not isinstance(source_base, str) or not re.fullmatch(
                r'[1-9]\d*/[1-9]\d*', source_base):
            raise ValueError('invalid source time base')
        source_base = Fraction(source_base)
        clip_base = Fraction(probe['time_base'])
        clip_pts = probe['pts']
        if source_base <= 0 or clip_base <= 0 or \
                not isinstance(clip_pts, list) or len(clip_pts) != len(pts) or \
                any(type(x) is not int for x in clip_pts) or \
                any(b <= a for a, b in zip(clip_pts, clip_pts[1:])):
            raise ValueError('invalid decoded clip timeline')
        for index in range(1, len(pts)):
            source_elapsed = (pts[index] - pts[0]) * source_base
            clip_elapsed = (clip_pts[index] - clip_pts[0]) * clip_base
            drift = abs(source_elapsed - clip_elapsed)
            adjacent_gaps = [(pts[index] - pts[index - 1]) * source_base]
            if index + 1 < len(pts):
                adjacent_gaps.append((pts[index + 1] - pts[index]) * source_base)
            # One tick from each representation bounds timestamp quantization.
            # Half the closest source gap is the strict index-identity bound:
            # a clip frame must not drift toward a neighbouring source frame.
            if drift > source_base + clip_base or 2 * drift >= min(adjacent_gaps):
                raise ValueError('resampled cadence or ambiguous frame identity')
        return {'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                'source_sha256_claim': source_hash,
                'source_time_base': str(source_base),
                'source_pts': pts,
                'cadence': 'relative_pts_within_quantization_and_index_bounds',
                'source_identity': 'receipt_claim_not_independently_verified'}
    except Exception:
        raise ClientError('native_receipt_invalid') from None


def decoded_frame_map(video_probe):
    """Label consecutive decoded clip frames; this cannot verify processor input."""
    try:
        frames = video_probe['decoded_frames']
        pts = video_probe['pts']
        time_base = video_probe['time_base']
        if type(frames) is not int or frames < 2 or not isinstance(pts, list) or \
                len(pts) != frames or any(type(p) is not int for p in pts) or \
                any(b <= a for a, b in zip(pts, pts[1:])) or \
                not isinstance(time_base, str) or not re.fullmatch(
                    r'[1-9]\d*/[1-9]\d*', time_base):
            raise ValueError('invalid decoded timeline')
        base = Fraction(time_base)
        timestamps = [f'{float((p - pts[0]) * base):.3f}' for p in pts]
        if len(set(timestamps)) != frames:
            raise ValueError('ambiguous display precision')
        return ', '.join(f'{i}={timestamp}s'
                         for i, timestamp in enumerate(timestamps, 1))
    except Exception:
        raise ClientError('video_preflight_failed') from None


def build_payload(video_bytes, video_probe, *, fresh_cache=False):
    frame_map = decoded_frame_map(video_probe)
    policy = video_input_policy(video_probe['width'], video_probe['height'],
                                video_probe['decoded_frames'])
    video_part = {'type': 'video_url', 'video_url': {
        'url': 'data:video/mp4;base64,' + base64.b64encode(video_bytes).decode('ascii')}}
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': PROMPT.replace('{frame_map}', frame_map)}, video_part]}],
        'reasoning_effort': 'xhigh', 'chat_template_kwargs': {'enable_thinking': True},
        'stream': True, 'stream_options': {'include_usage': True},
        'media_io_kwargs': policy['media_io_kwargs'],
        'mm_processor_kwargs': policy['mm_processor_kwargs']}
    if fresh_cache:
        payload['cache_salt'] = uuid.uuid4().hex
        video_part['uuid'] = uuid.uuid4().hex
    return payload, policy['audit']


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, route, *, timeout=3600):
        super().__init__(route['host'], route['port'], timeout=timeout,
                         context=ssl.create_default_context())
        self._pinned_ip = route['ip']

    def connect(self):
        raw = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _parse_event(data, thought, answer, metadata):
    if data == '[DONE]':
        return True
    try:
        event = json.loads(data, object_pairs_hook=_unique_json_pairs)
        if not isinstance(event, dict) or 'error' in event:
            raise ValueError('stream error')
        reported_model = event.get('model')
        if reported_model is not None and reported_model != MODEL:
            raise ValueError('response model drift')
        for key in ('id', 'model', 'system_fingerprint', 'usage'):
            if event.get(key) is not None:
                metadata[key] = event[key]
        choices = event.get('choices', [])
        if not isinstance(choices, list):
            raise ValueError('invalid choices')
        for choice in choices:
            delta = choice.get('delta', {})
            reasoning = delta.get('reasoning') or delta.get('reasoning_content') or ''
            content = delta.get('content') or ''
            finish = choice.get('finish_reason')
            if not isinstance(reasoning, str) or not isinstance(content, str) or \
                    (finish is not None and (not isinstance(finish, str) or not finish)):
                raise ValueError('invalid content')
            thought.append(reasoning)
            answer.append(content)
            if finish:
                metadata['finish_reason'] = finish
    except Exception:
        raise ClientError('stream_invalid') from None
    return False


def stream_request(route, payload, events_path, *, connection_factory=PinnedHTTPSConnection):
    headers = {'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
    if route['key']:
        headers['Authorization'] = 'Bearer ' + route['key']
    connection = connection_factory(route)
    thought, answer, metadata = [], [], {}
    try:
        connection.request('POST', '/v1/chat/completions',
                           json.dumps(payload).encode('utf-8'), headers)
        response = connection.getresponse()
        if response.status != 200:
            # 3xx are rejected, never followed; error bodies may contain secrets.
            category = ('redirect_refused' if 300 <= response.status < 400 else
                        'rate_limited' if response.status == 429 else 'http_error')
            raise ClientError(category)
        content_type = response.getheader('Content-Type')
        if not isinstance(content_type, str) or \
                content_type.split(';', 1)[0].strip().lower() != 'text/event-stream':
            raise ClientError('stream_invalid')
        data = []
        pending_lines = []
        done = False
        with events_path.open('xb') as events:
            for line in response:
                pending_lines.append(line)
                try:
                    text = line.decode('utf-8').rstrip('\r\n')
                except UnicodeError:
                    raise ClientError('stream_invalid') from None
                if text.startswith('data:'):
                    data.append(text[5:].lstrip(' '))
                elif text.startswith('event:'):
                    if text[6:].strip() not in ('', 'message'):
                        raise ClientError('stream_invalid')
                elif not text:
                    if data:
                        # Validate before saving an SSE event: error payloads
                        # can carry server-side credentials or route details.
                        done = _parse_event('\n'.join(data), thought, answer, metadata)
                        data = []
                    events.writelines(pending_lines)
                    events.flush()
                    pending_lines = []
                    if done:
                        break
                elif not text.startswith((':', 'id:', 'retry:')):
                    raise ClientError('stream_invalid')
            # An SSE event is dispatched only by its blank terminator. Do not
            # accept or retain an unterminated final event, including [DONE].
        return {'state': 'response_received_unreviewed' if done and
                metadata.get('finish_reason') else 'incomplete_stream',
                'response': {'metadata': metadata, 'reasoning': ''.join(thought),
                             'content': ''.join(answer),
                             'trust': 'untrusted_model_output'},
                'raw_sse': events_path.name}
    finally:
        connection.close()


def _save(record_path, record, *, first=False):
    data = json.dumps(record, ensure_ascii=False, indent=2) + '\n'
    temporary = record_path.with_name(record_path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as output:
            output.write(data)
        if first:
            # An atomic no-overwrite publish: even concurrent readers cannot
            # observe a partially written initial record.
            os.link(temporary, record_path)
        else:
            temporary.replace(record_path)
    except OSError:
        raise ClientError('output_write_failed') from None
    finally:
        temporary.unlink(missing_ok=True)


def run(args, *, resolver=socket.getaddrinfo,
        connection_factory=PinnedHTTPSConnection):
    workspace = Path(args.workspace).resolve(strict=True)
    video = Path(args.video).resolve(strict=True)
    output = Path(args.output).resolve()
    if not video.is_relative_to(workspace) or not output.is_relative_to(workspace) or \
            not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', args.source_id) or \
            not 0 <= args.start < 24 * 3600:
        raise ClientError('input_invalid')
    events = output.with_suffix('.events.sse')
    if output.exists() or events.exists():
        raise ClientError('output_exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {'client_version': CLIENT_VERSION,
              'source_id': args.source_id, 'source_start_seconds': args.start,
              'model': MODEL, 'input_mode': 'video', 'reasoning_effort': 'xhigh',
              'enable_thinking': True, 'request_output_limit': None,
              'model_output_trust': 'untrusted_research_data',
              'source_native_cadence': 'not_proven_by_client',
              'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'state': 'preflight'}
    _save(output, record, first=True)
    try:
        raw = _read_clip(video)
        record.update({'clip_sha256': hashlib.sha256(raw).hexdigest(),
                       'clip_bytes': len(raw)})
        probe = probe_video(video)
        # ffprobe opens the pathname independently of our earlier read. Refuse
        # a clip changed between that probe and the bytes we will attach.
        if _read_clip(video) != raw:
            raise ClientError('video_preflight_failed')
        record['decoded_video'] = probe
        record['native_pts_receipt'] = validate_native_receipt(
            args.native_pts_receipt, workspace, record['clip_sha256'], probe)
        record['source_native_cadence'] = 'receipt_quantization_check_source_unverified'
        payload, policy = build_payload(raw, probe, fresh_cache=args.fresh_cache)
        route = load_route(args.config_path, args.route_pin, workspace, resolver=resolver)
        record['video_input_policy'] = policy
        record['processor_sampling_requested'] = False
        record['server_sampling_verified'] = False
        record['state'] = 'requesting'
        _save(output, record)
        record.update(stream_request(route, payload, events,
                                     connection_factory=connection_factory))
    except ClientError as error:
        record.update({'state': 'blocked', 'error_category': error.category})
    except Exception:
        record.update({'state': 'blocked', 'error_category': 'request_failed'})
    _save(output, record)
    return record['state'] == 'response_received_unreviewed', {
        'state': record['state'], **({'error_category': record['error_category']}
                                    if 'error_category' in record else {})}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video')
    parser.add_argument('output')
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--start', type=float, required=True)
    parser.add_argument('--workspace', default='/workspace')
    parser.add_argument('--route-pin', required=True,
                        help='Protected operator-reviewed route pin outside the workspace')
    parser.add_argument('--native-pts-receipt', required=True,
                        help='Source/clip frame PTS mapping for this exact video')
    parser.add_argument('--fresh-cache', action='store_true')
    args = parser.parse_args(argv)
    args.config_path = Path.home() / '.omp/agent/models.yml'
    try:
        okay, status = run(args)
    except ClientError as error:
        okay, status = False, {'state': 'blocked', 'error_category': error.category}
    except Exception:
        okay, status = False, {'state': 'blocked', 'error_category': 'input_invalid'}
    print(json.dumps(status))
    return 0 if okay else 1


if __name__ == '__main__':
    raise SystemExit(main())
