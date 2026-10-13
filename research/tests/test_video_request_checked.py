"""Offline request-safety tests; no model, DNS, or network is contacted."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'remote'))
import video_request_checked as client


PROBE = {'width': 512, 'height': 288, 'duration_seconds': 1.0,
         'decoded_frames': 30, 'time_base': '1/30000',
         'pts': [i * 1000 for i in range(30)]}
SECRET = 'PRIVATE-KEY-DO-NOT-LOG-8657'
HOST = 'selfhost.example.invalid'
BASE = f'https://{HOST}/v1'
IP = '100.64.10.23'


def resolver(host, port, **kwargs):
    assert host == HOST and port == 443
    return [(None, None, None, None, (IP, port))]


def showinfo_log(pts=None, *, duration='00:00:01.00', time_base='1/30000',
                 dimensions=None, frame_numbers=None):
    pts = pts if pts is not None else PROBE['pts']
    dimensions = dimensions or [(512, 288)] * len(pts)
    frame_numbers = frame_numbers if frame_numbers is not None else range(len(pts))
    lines = [f'  Duration: {duration}, start: 0.000000, bitrate: 100 kb/s',
             f'[Parsed_showinfo_0 @ 0xabc123] config in time_base: {time_base}, frame_rate: 30/1']
    lines.extend(
        f'[Parsed_showinfo_0 @ 0xabc123] n: {index} pts: {timestamp} '
        f'pts_time:{timestamp / 30000 if isinstance(timestamp, int) else 0} '
        f'fmt:yuv420p s:{width}x{height} i:P'
        for index, timestamp, (width, height) in zip(frame_numbers, pts, dimensions))
    return ('\n'.join(lines) + '\n').encode()


class FakeConnection:
    def __init__(self, route, *, status=200, lines=None):
        self.route = route
        self.status = status
        self.lines = lines or [
            b'data: {"model":"[redacted model]","choices":[{"delta":{"reasoning_content":"think","content":"answer"},"finish_reason":"stop"}]}\n',
            b'\n', b'data: [DONE]\n', b'\n']
        self.requests = []
        self.closed = False

    def request(self, method, path, body, headers):
        self.requests.append((method, path, json.loads(body), headers))

    def getresponse(self):
        return SimpleNamespace(status=self.status, __iter__=lambda: iter(self.lines))

    def close(self):
        self.closed = True


class Response:
    def __init__(self, status, lines, content_type='text/event-stream; charset=utf-8'):
        self.status = status
        self.lines = lines
        self.content_type = content_type

    def __iter__(self):
        return iter(self.lines)

    def getheader(self, name):
        return self.content_type if name.lower() == 'content-type' else None


class CheckedVideoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.video = self.workspace / 'short.mp4'
        self.video.write_bytes(b'fake clip bytes')
        self.output = self.workspace / 'out.json'
        self.receipt = self.workspace / 'native-pts.json'
        self.receipt.write_text(json.dumps({
            'version': 1, 'clip_sha256': hashlib.sha256(self.video.read_bytes()).hexdigest(),
            'source_sha256': 'a' * 64, 'source_time_base': '1/30000',
            'source_pts': PROBE['pts']}))
        self.config = self.root / 'models.yml'
        self.pin = self.root / 'pin.json'
        self.setup_route()

    def setup_route(self, *, base=BASE, model=client.MODEL, key=SECRET,
                    pin_base=BASE, addresses=None, provider=client.PROVIDER):
        self.config.write_text(json.dumps({'providers': {client.PROVIDER: {
            'baseUrl': base, 'models': [{'id': model}], 'apiKey': key}}}))
        self.pin.write_text(json.dumps({'provider': provider, 'model': client.MODEL,
            'route_kind': 'operator_verified_direct_self_hosted',
            'base_url': pin_base, 'allowed_ips': addresses or [IP]}))
        if os.name == 'posix':
            self.pin.chmod(0o600)
            self.config.chmod(0o600)

    def args(self):
        return SimpleNamespace(video=str(self.video), output=str(self.output),
            source_id='public-study-01', start=12.5, workspace=str(self.workspace),
            route_pin=str(self.pin), native_pts_receipt=str(self.receipt),
            config_path=self.config, fresh_cache=False)

    def test_exact_route_and_private_address_required(self):
        route = client.load_route(self.config, self.pin, self.workspace,
                                  resolver=resolver)
        self.assertEqual(route['ip'], IP)
        self.assertEqual(route['key'], SECRET)
        for change in ({'model': 'other'}, {'provider': 'other'},
                       {'base': 'https://somewhere.example.invalid/v1'},
                       {'pin_base': 'https://somewhere.example.invalid/v1'},
                       {'base': 'http://' + HOST + '/v1',
                        'pin_base': 'http://' + HOST + '/v1'}):
            with self.subTest(change=change):
                self.setup_route(**change)
                with self.assertRaises(client.ClientError):
                    client.load_route(self.config, self.pin, self.workspace,
                                      resolver=resolver)
        self.setup_route()
        with self.assertRaisesRegex(client.ClientError, 'route_address_mismatch'):
            client.load_route(self.config, self.pin, self.workspace,
                resolver=lambda *a, **k: [(None, None, None, None,
                                           ('8.8.8.8', 443))])
        with self.assertRaisesRegex(client.ClientError, 'route_address_mismatch'):
            client.load_route(self.config, self.pin, self.workspace,
                resolver=lambda *a, **k: [(None, None, None, None, (IP, 443)),
                                           (None, None, None, None,
                                            ('8.8.8.8', 443))])

    def test_route_rejects_invalid_port_header_and_ambiguous_pin(self):
        self.setup_route(base=BASE.replace('/v1', ':0/v1'),
                         pin_base=BASE.replace('/v1', ':0/v1'))
        with self.assertRaisesRegex(client.ClientError, 'route_config_invalid'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)
        self.setup_route(key=SECRET + '\x00')
        with self.assertRaisesRegex(client.ClientError,
                                    'credential_missing_or_unresolved'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)
        self.setup_route()
        pin = self.pin.read_text()
        self.pin.write_text(pin[:-1] + ',"model":"other"}')
        with self.assertRaisesRegex(client.ClientError,
                                    'route_pin_missing_or_invalid'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)
        self.setup_route()
        config = self.config.read_text()
        self.config.write_text(config[:-3] + ',"baseUrl":"' + BASE + '"}}}')
        with self.assertRaisesRegex(ValueError, 'duplicate YAML key'):
            client.yaml.load(self.config.read_text(), Loader=client._UniqueYAMLLoader)
        with self.assertRaisesRegex(client.ClientError, 'route_config_invalid'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)

    def test_protected_configuration_and_pin_cannot_be_in_workspace(self):
        for source in (self.config, self.pin):
            with self.subTest(source=source.name):
                copy = self.workspace / source.name
                copy.write_bytes(source.read_bytes())
                with self.assertRaises(client.ClientError):
                    client.load_route(copy if source == self.config else self.config,
                                      copy if source == self.pin else self.pin,
                                      self.workspace, resolver=resolver)

    def test_private_readonly_config_exception_is_narrow(self):
        home = self.root / 'private-home'
        agent = home / '.omp' / 'agent'
        agent.mkdir(parents=True)
        config = agent / 'models.yml'
        config.write_text(self.config.read_text())
        modes = {home: 0o755, home / '.omp': 0o755,
                 agent: 0o700, config: 0o644}
        owners = {path: 1000 for path in modes}
        links = {config: 1}
        original_stat = Path.stat
        def synthetic_stat(path, *args, **kwargs):
            if path in modes:
                kind = stat.S_IFREG if path == config else stat.S_IFDIR
                return SimpleNamespace(st_mode=kind | modes[path],
                                       st_uid=owners[path],
                                       st_nlink=links.get(path, 1))
            return original_stat(path, *args, **kwargs)
        mount = SimpleNamespace(f_flag=1)
        with mock.patch.object(Path, 'home', return_value=home), \
             mock.patch.object(Path, 'stat', autospec=True,
                               side_effect=synthetic_stat), \
             mock.patch.object(client.os, 'statvfs', return_value=mount,
                               create=True), \
             mock.patch.object(client.os, 'access', return_value=False) as access:
            self.assertTrue(client._config_permissions_ok(
                config, synthetic_stat(config), posix=True, owner_uid=1000))
            self.assertTrue(client._owner_private_readonly_config(config, 1000))
            modes[agent] = 0o755
            self.assertFalse(client._owner_private_readonly_config(config, 1000))
            modes[agent] = 0o700
            modes[home / '.omp'] = 0o775
            self.assertFalse(client._owner_private_readonly_config(config, 1000))
            modes[home / '.omp'] = 0o755
            modes[config] = 0o664
            self.assertFalse(client._owner_private_readonly_config(config, 1000))
            modes[config] = 0o644
            owners[config] = 1001
            self.assertFalse(client._owner_private_readonly_config(config, 1000))
            owners[config] = 1000
            links[config] = 2
            self.assertFalse(client._owner_private_readonly_config(config, 1000))
            links[config] = 1
            mount.f_flag = 0
            access.return_value = True
            self.assertFalse(client._owner_private_readonly_config(config, 1000))
            mount.f_flag = 1
            access.return_value = False
            outside = self.root / 'outside.yml'
            outside.write_text(self.config.read_text())
            self.assertFalse(client._owner_private_readonly_config(outside, 1000))

    @unittest.skipUnless(os.name == 'posix', 'POSIX file-mode rule')
    def test_route_pin_still_requires_mode_0600(self):
        self.pin.chmod(0o644)
        with self.assertRaisesRegex(client.ClientError,
                                    'route_pin_missing_or_invalid'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)

    @unittest.skipUnless(os.name == 'posix', 'POSIX private bind-mount rule')
    def test_readonly_private_yaml_loads_but_public_parent_fails(self):
        home = self.root / 'private-home'
        agent = home / '.omp' / 'agent'
        agent.mkdir(parents=True)
        home.chmod(0o755)
        (home / '.omp').chmod(0o755)
        agent.chmod(0o700)
        config = agent / 'models.yml'
        config.write_text(self.config.read_text())
        config.chmod(0o644)
        with mock.patch.object(Path, 'home', return_value=home), \
             mock.patch.object(client.os, 'statvfs',
                               return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            loaded = client._read_protected_yaml(config, self.workspace)
            self.assertIn(client.PROVIDER, loaded['providers'])
            agent.chmod(0o755)
            with self.assertRaisesRegex(client.ClientError, 'route_config_invalid'):
                client._read_protected_yaml(config, self.workspace)

    def test_missing_key_missing_pin_and_config_error_are_sanitized(self):
        self.setup_route(key='')
        with self.assertRaisesRegex(client.ClientError, 'credential_missing_or_unresolved'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)
        self.setup_route()
        self.pin.unlink()
        with self.assertRaisesRegex(client.ClientError, 'route_pin_missing_or_invalid'):
            client.load_route(self.config, self.pin, self.workspace,
                              resolver=resolver)
        self.setup_route()
        self.config.write_text('invalid: [ ' + SECRET)
        with mock.patch.object(client, 'probe_video', return_value=PROBE):
            okay, status = client.run(self.args(), resolver=resolver)
        self.assertFalse(okay)
        self.assertEqual(status, {'state': 'blocked',
                                  'error_category': 'route_config_invalid'})
        self.assertNotIn(SECRET, self.output.read_text())
        self.assertNotIn(HOST, self.output.read_text())

    def test_video_payload_preserves_all_frames_and_unlimited_thinking(self):
        payload, audit = client.build_payload(b'clip', PROBE)
        self.assertEqual(payload['model'], client.MODEL)
        self.assertEqual(payload['reasoning_effort'], 'xhigh')
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': True})
        self.assertTrue(payload['stream'])
        self.assertNotIn('max_tokens', payload)
        self.assertNotIn('max_completion_tokens', payload)
        self.assertNotIn('max_output_tokens', payload)
        self.assertEqual(payload['media_io_kwargs']['video']['num_frames'], 30)
        self.assertIs(payload['mm_processor_kwargs']['do_sample_frames'], False)
        self.assertEqual(audit['requested_frames'], 30)
        content = payload['messages'][0]['content']
        self.assertEqual([part['type'] for part in content], ['text', 'video_url'])
        self.assertIn('data:video/mp4;base64,', content[1]['video_url']['url'])

    def test_mock_request_raw_sse_and_untrusted_output_without_config_leak(self):
        instance = FakeConnection(None)
        instance.getresponse = lambda: Response(200, instance.lines)
        with mock.patch.object(client, 'probe_video', return_value=PROBE):
            with contextlib.redirect_stdout(io.StringIO()) as output_text:
                okay, status = client.run(self.args(), resolver=resolver,
                                          connection_factory=lambda route: instance)
        self.assertTrue(okay)
        self.assertEqual(status, {'state': 'response_received_unreviewed'})
        method, path, payload, headers = instance.requests[0]
        self.assertEqual((method, path), ('POST', '/v1/chat/completions'))
        self.assertEqual(headers['Authorization'], 'Bearer ' + SECRET)
        self.assertEqual(payload['media_io_kwargs']['video']['num_frames'], 30)
        record = json.loads(self.output.read_text())
        self.assertEqual(record['response']['content'], 'answer')
        self.assertEqual(record['response']['reasoning'], 'think')
        self.assertEqual(record['response']['trust'], 'untrusted_model_output')
        self.assertEqual(record['decoded_video']['pts'], PROBE['pts'])
        self.assertEqual(record['native_pts_receipt']['cadence'],
                         'relative_pts_within_quantization_and_index_bounds')
        self.assertEqual((self.workspace / record['raw_sse']).read_bytes(),
                         b''.join(instance.lines))
        self.assertNotIn(SECRET, self.output.read_text() + output_text.getvalue())
        self.assertNotIn(HOST, self.output.read_text() + output_text.getvalue())
        self.assertTrue(instance.closed)

    def test_incomplete_stream_never_reports_success(self):
        for ending in ([], [b'data: [DONE]\n', b'\n']):
            with self.subTest(ending=ending):
                lines = [b': heartbeat\n', b'\n',
                         b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n',
                         b'\n'] + ending
                instance = FakeConnection(None, lines=lines)
                instance.getresponse = lambda: Response(200, lines)
                with mock.patch.object(client, 'probe_video', return_value=PROBE):
                    okay, status = client.run(self.args(), resolver=resolver,
                                              connection_factory=lambda route: instance)
                self.assertFalse(okay)
                self.assertEqual(status['state'], 'incomplete_stream')
                record = json.loads(self.output.read_text())
                self.assertEqual(record['response']['content'], 'partial')
                self.assertEqual((self.workspace / record['raw_sse']).read_bytes(),
                                 b''.join(lines))
                self.output.unlink()
                self.output.with_suffix('.events.sse').unlink()
        lines = [b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"stop"}]}\n',
                 b'\n']
        instance = FakeConnection(None, lines=lines)
        instance.getresponse = lambda: Response(200, lines)
        with mock.patch.object(client, 'probe_video', return_value=PROBE):
            okay, status = client.run(self.args(), resolver=resolver,
                                      connection_factory=lambda route: instance)
        self.assertFalse(okay)
        self.assertEqual(status['state'], 'incomplete_stream')

    def test_json_response_and_sse_error_are_sanitized(self):
        for lines, content_type in (([SECRET.encode() + b'\n'], 'application/json'),
                                    ([b'data: {"error":"' + SECRET.encode() + b'"}\n',
                                      b'\n'], 'text/event-stream')):
            with self.subTest(content_type=content_type):
                instance = FakeConnection(None, lines=lines)
                instance.getresponse = lambda: Response(200, lines, content_type)
                with mock.patch.object(client, 'probe_video', return_value=PROBE):
                    okay, status = client.run(self.args(), resolver=resolver,
                                              connection_factory=lambda route: instance)
                self.assertFalse(okay)
                self.assertEqual(status['error_category'], 'stream_invalid')
                self.assertNotIn(SECRET, self.output.read_text())
                events = self.output.with_suffix('.events.sse')
                if events.exists():
                    self.assertNotIn(SECRET.encode(), events.read_bytes())
                self.output.unlink()
                if events.exists():
                    events.unlink()

    def test_empty_error_object_and_invalid_delta_are_rejected(self):
        for bad in (b'{"error":{}}',
                    b'{"choices":[{"delta":{"content":{"secret":"x"}}}]}'):
            with self.subTest(bad=bad):
                lines = [b'data: ' + bad + b'\n', b'\n']
                instance = FakeConnection(None)
                instance.getresponse = lambda: Response(200, lines)
                with mock.patch.object(client, 'probe_video', return_value=PROBE):
                    okay, status = client.run(self.args(), resolver=resolver,
                                              connection_factory=lambda route: instance)
                self.assertFalse(okay)
                self.assertEqual(status['error_category'], 'stream_invalid')
                self.assertEqual(self.output.with_suffix('.events.sse').read_bytes(), b'')
                self.output.unlink()
                self.output.with_suffix('.events.sse').unlink()

    def test_named_error_sse_event_is_rejected_even_with_valid_json(self):
        lines = [b'event: error\n',
                 b'data: {"choices":[{"delta":{"content":"wrong"},"finish_reason":"stop"}]}\n',
                 b'\n', b'data: [DONE]\n', b'\n']
        instance = FakeConnection(None)
        instance.getresponse = lambda: Response(200, lines)
        with mock.patch.object(client, 'probe_video', return_value=PROBE):
            okay, status = client.run(self.args(), resolver=resolver,
                                      connection_factory=lambda route: instance)
        self.assertFalse(okay)
        self.assertEqual(status['error_category'], 'stream_invalid')
        self.assertEqual(self.output.with_suffix('.events.sse').read_bytes(), b'')

    def test_sse_rejects_duplicate_model_key_and_unterminated_done(self):
        completed = (b'data: {"choices":[{"delta":{"content":"answer"},'
                     b'"finish_reason":"stop"}]}\n\n')
        cases = (
            (b'data: {"model":"other","model":"' + client.MODEL.encode() +
             b'","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
             b'data: [DONE]\n\n', 'stream_invalid'),
            (completed + b'data: [DONE]\n', 'incomplete_stream'),
        )
        for index, (raw, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                self.output = self.workspace / f'out-{index}.json'
                lines = raw.splitlines(keepends=True)
                instance = FakeConnection(None)
                instance.getresponse = lambda: Response(200, lines)
                with mock.patch.object(client, 'probe_video', return_value=PROBE):
                    okay, status = client.run(self.args(), resolver=resolver,
                                              connection_factory=lambda route: instance)
                self.assertFalse(okay)
                self.assertEqual(status.get('error_category', status['state']), expected)
                self.assertEqual(self.output.with_suffix('.events.sse').read_bytes(),
                                 b'' if expected == 'stream_invalid' else completed)

    def test_redirect_is_rejected_without_following_or_logging_location(self):
        for code in (301, 302, 307, 308):
            with self.subTest(code=code):
                instance = FakeConnection(None, status=code)
                instance.getresponse = lambda: Response(code,
                    [b'Location: https://evil/\n'])
                with mock.patch.object(client, 'probe_video', return_value=PROBE):
                    okay, status = client.run(self.args(), resolver=resolver,
                                              connection_factory=lambda route: instance)
                self.assertFalse(okay)
                self.assertEqual(status['error_category'], 'redirect_refused')
                self.assertNotIn('evil', self.output.read_text())
                self.assertFalse(self.output.with_suffix('.events.sse').exists())
                self.output.unlink()

    def test_429_is_a_sanitized_stop_category(self):
        instance = FakeConnection(None, status=429)
        instance.getresponse = lambda: Response(429, [SECRET.encode()])
        with mock.patch.object(client, 'probe_video', return_value=PROBE):
            okay, status = client.run(self.args(), resolver=resolver,
                                      connection_factory=lambda route: instance)
        self.assertFalse(okay)
        self.assertEqual(status['error_category'], 'rate_limited')
        self.assertNotIn(SECRET, self.output.read_text())

    def test_probe_reads_decoded_pts_without_resampling(self):
        result = SimpleNamespace(stdout=json.dumps({
            'streams': [{'width': 512, 'height': 288, 'time_base': '1/30000'}],
            'format': {'duration': '1.0'}, 'frames': [
                {'media_type': 'video', 'best_effort_timestamp': str(i * 1000)}
                for i in range(30)]}).encode())
        with mock.patch.object(client.subprocess, 'run', return_value=result) as probe:
            observed = client.probe_video(self.video)
        command = probe.call_args.args[0]
        self.assertEqual(command[0], 'ffprobe')
        self.assertIn('-show_frames', command)
        self.assertEqual(observed['decoded_frames'], 30)
        self.assertEqual(observed['pts'], PROBE['pts'])
        self.assertNotIn('-r', command)

    def test_probe_rejects_invalid_duration_frame_count_and_pts(self):
        baseline = {
            'streams': [{'width': 512, 'height': 288, 'time_base': '1/30000'}],
            'format': {'duration': '1.0'},
            'frames': [{'media_type': 'video',
                        'best_effort_timestamp': str(i * 1000)} for i in range(30)],
        }
        mutations = (
            lambda info: info['format'].update(duration='0.4'),
            lambda info: info['format'].update(duration='1.7'),
            lambda info: info.update(frames=info['frames'][:1]),
            lambda info: info['frames'][7].update(best_effort_timestamp='6000'),
            lambda info: info['streams'][0].update(time_base='0/30000'),
            lambda info: info['streams'][0].update(width=0),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                info = json.loads(json.dumps(baseline))
                mutate(info)
                with mock.patch.object(client.subprocess, 'run',
                    return_value=SimpleNamespace(stdout=json.dumps(info).encode())):
                    with self.assertRaisesRegex(client.ClientError,
                                                'video_preflight_failed'):
                        client.probe_video(self.video)

    def test_ffmpeg_showinfo_fallback_decodes_without_sampling(self):
        commands = []
        def run(command, **kwargs):
            commands.append((command, kwargs))
            if command[0] == 'ffprobe':
                raise FileNotFoundError('ffprobe unavailable')
            self.assertEqual(command[0], 'bundled-ffmpeg')
            return SimpleNamespace(stderr=showinfo_log(),
                                   stdout=b'frame=30\nprogress=end\n')
        with mock.patch.object(client, '_ffmpeg_executable',
                               return_value='bundled-ffmpeg'), \
             mock.patch.object(client.subprocess, 'run', side_effect=run):
            observed = client.probe_video(self.video)
        self.assertEqual(observed, PROBE)
        command, kwargs = commands[1]
        self.assertEqual(command[command.index('-vf') + 1], 'showinfo')
        self.assertEqual(command[command.index('-fps_mode') + 1], 'passthrough')
        self.assertEqual(command[command.index('-map') + 1], '0:v:0')
        self.assertEqual(command[command.index('-progress') + 1], 'pipe:1')
        self.assertIn('-copyts', command)
        self.assertIn('-noautorotate', command)
        self.assertNotIn('-r', command)
        self.assertNotIn('fps', command)
        self.assertEqual(kwargs, {'capture_output': True, 'check': True,
                                  'timeout': 30})

    def test_ffmpeg7_shaped_showinfo_and_progress_blocks(self):
        log = showinfo_log().replace(
            b'fmt:yuv420p s:512x288 i:P',
            b'pos:48 fmt:yuv420p sar:1/1 s:512x288 i:P iskey:1 type:I '
            b'checksum:01234567')
        progress = (b'frame=12\nfps=0.0\nstream_0_0_q=-0.0\n'
                    b'out_time_us=400000\nprogress=continue\n'
                    b'frame=30\nfps=0.0\nstream_0_0_q=-0.0\n'
                    b'out_time_us=1000000\nprogress=end\n')
        def run(command, **kwargs):
            if command[0] == 'ffprobe':
                raise FileNotFoundError('ffprobe unavailable')
            return SimpleNamespace(stderr=log, stdout=progress)
        with mock.patch.object(client, '_ffmpeg_executable',
                               return_value='bundled-ffmpeg'), \
             mock.patch.object(client.subprocess, 'run', side_effect=run):
            self.assertEqual(client.probe_video(self.video), PROBE)

    def test_ffmpeg_showinfo_missing_or_ambiguous_fields_fail_closed(self):
        good = showinfo_log()
        mutations = (
            good.replace(b'Duration: 00:00:01.00', b'Duration: N/A'),
            good.replace(b'Duration: 00:00:01.00', b'Duration: 00:00:01.7'),
            good.replace(b'Duration: 00:00:01.00', b'Duration: 00:00:00.50'),
            good.replace(b'Duration: 00:00:01.00', b'Duration: 00:00:01.60'),
            good.replace(b'config in time_base:', b'config in timebase:'),
            good.replace(b'config in time_base: 1/30000',
                         b'config in time_base: 0/30000'),
            good + b'[Parsed_showinfo_0 @ 0xabc123] config in time_base: 1/30000, frame_rate: 30/1\n',
            good.replace(b'n: 7 pts:', b'n: 8 pts:'),
            good.replace(b'n: 7 pts: 7000', b'n: 7 pts: N/A'),
            good.replace(b's:512x288', b's:640x360', 1),
            showinfo_log(pts=[0]),
            showinfo_log(pts=[0, 1000, 1000] + PROBE['pts'][3:]),
            showinfo_log(pts=list(range(121)), time_base='1/30000'),
            showinfo_log(pts=[i * 100000 for i in range(30)]),
        )
        for log in mutations:
            with self.subTest(log_tail=log[-90:]):
                def run(command, **kwargs):
                    if command[0] == 'ffprobe':
                        raise FileNotFoundError('ffprobe unavailable')
                    return SimpleNamespace(stderr=log,
                                           stdout=b'frame=30\nprogress=end\n')
                with mock.patch.object(client, '_ffmpeg_executable',
                                       return_value='bundled-ffmpeg'), \
                     mock.patch.object(client.subprocess, 'run', side_effect=run):
                    with self.assertRaisesRegex(client.ClientError,
                                                'video_preflight_failed'):
                        client.probe_video(self.video)

    def test_ffmpeg_progress_must_match_showinfo_count(self):
        for progress in (b'', b'frame=29\nprogress=end\n',
                         b'frame=30\nprogress=continue\n',
                         b'frame=30\nprogress=end\nprogress=end\n',
                         b'frame=29\nframe=30\nprogress=end\n',
                         b'progress=continue\nframe=30\nprogress=end\n'):
            with self.subTest(progress=progress):
                def run(command, **kwargs):
                    if command[0] == 'ffprobe':
                        raise FileNotFoundError('ffprobe unavailable')
                    return SimpleNamespace(stderr=showinfo_log(),
                                           stdout=progress)
                with mock.patch.object(client, '_ffmpeg_executable',
                                       return_value='bundled-ffmpeg'), \
                     mock.patch.object(client.subprocess, 'run', side_effect=run):
                    with self.assertRaisesRegex(client.ClientError,
                                                'video_preflight_failed'):
                        client.probe_video(self.video)

    def test_ffmpeg_showinfo_mixed_filter_instance_fails_closed(self):
        mixed = showinfo_log().replace(
            b'[Parsed_showinfo_0 @ 0xabc123] n:',
            b'[Parsed_showinfo_0 @ 0xdef456] n:')
        def run(command, **kwargs):
            if command[0] == 'ffprobe':
                raise FileNotFoundError('ffprobe unavailable')
            return SimpleNamespace(stderr=mixed,
                                   stdout=b'frame=30\nprogress=end\n')
        with mock.patch.object(client, '_ffmpeg_executable',
                               return_value='bundled-ffmpeg'), \
             mock.patch.object(client.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(client.ClientError,
                                        'video_preflight_failed'):
                client.probe_video(self.video)

    def test_existing_broken_ffprobe_does_not_fallback_or_leak_error(self):
        with mock.patch.object(client.subprocess, 'run',
            side_effect=client.subprocess.CalledProcessError(
                1, 'ffprobe', stderr=SECRET.encode())), \
             mock.patch.object(client, '_ffmpeg_executable',
                               side_effect=AssertionError('must not fallback')):
            with self.assertRaises(client.ClientError) as captured:
                client.probe_video(self.video)
        self.assertEqual(captured.exception.category, 'video_preflight_failed')
        self.assertNotIn(SECRET, str(captured.exception))

    def test_video_preflight_exception_does_not_expose_decoder_detail(self):
        with mock.patch.object(client.subprocess, 'run',
                               side_effect=RuntimeError(SECRET + ' decoder path')):
            with self.assertRaises(client.ClientError) as captured:
                client.probe_video(self.video)
        self.assertEqual(captured.exception.category, 'video_preflight_failed')
        self.assertNotIn(SECRET, str(captured.exception))
        with mock.patch.object(client.subprocess, 'run',
                               side_effect=RuntimeError(SECRET + ' decoder path')):
            okay, status = client.run(self.args(), resolver=resolver,
                connection_factory=lambda route: self.fail('must not send'))
        self.assertFalse(okay)
        self.assertEqual(status['error_category'], 'video_preflight_failed')
        self.assertNotIn(SECRET, self.output.read_text())

    def test_cadence_or_clip_hash_mismatch_fails_before_network(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['source_pts'][7] += 3
        self.receipt.write_text(json.dumps(receipt))
        with mock.patch.object(client, 'probe_video', return_value=PROBE):
            okay, status = client.run(self.args(), resolver=resolver,
                connection_factory=lambda route: self.fail('must not send'))
        self.assertFalse(okay)
        self.assertEqual(status['error_category'], 'native_receipt_invalid')
        self.assertFalse(self.output.with_suffix('.events.sse').exists())

    def test_native_receipt_accepts_integer_pts_quantization(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['source_time_base'] = '1/16000'
        receipt['source_pts'] = [round(i * 16000 / 30) for i in range(30)]
        self.receipt.write_text(json.dumps(receipt))
        for base, pts in (('1/30', list(range(30))),
                          ('1/1000', [round(i * 1000 / 30) for i in range(30)])):
            with self.subTest(clip_time_base=base):
                probe = {**PROBE, 'time_base': base, 'pts': pts}
                result = client.validate_native_receipt(
                    self.receipt, self.workspace, receipt['clip_sha256'], probe)
                self.assertEqual(result['source_pts'], receipt['source_pts'])
                self.assertEqual(result['cadence'],
                                 'relative_pts_within_quantization_and_index_bounds')

    def test_receipt_rejects_25fps_drift_and_dropped_frame(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['source_time_base'] = '1/16000'
        receipt['source_pts'] = [round(i * 16000 / 30) for i in range(30)]
        self.receipt.write_text(json.dumps(receipt))
        cases = (
            {**PROBE, 'time_base': '1/1000', 'pts': [i * 40 for i in range(30)]},
            {**PROBE, 'time_base': '1/30',
             'pts': [round(i * 30 / 25) for i in range(30)]},
            {**PROBE, 'time_base': '1/30',
             'pts': list(range(7)) + [i + 1 for i in range(7, 30)]},
        )
        for probe in cases:
            with self.subTest(clip_time_base=probe['time_base']):
                with self.assertRaisesRegex(client.ClientError,
                                            'native_receipt_invalid'):
                    client.validate_native_receipt(
                        self.receipt, self.workspace, receipt['clip_sha256'], probe)

    def test_receipt_rejects_exact_half_frame_gap(self):
        clip_pts = PROBE['pts'].copy()
        clip_pts[7] += 500
        with self.assertRaisesRegex(client.ClientError, 'native_receipt_invalid'):
            client.validate_native_receipt(
                self.receipt, self.workspace,
                json.loads(self.receipt.read_text())['clip_sha256'],
                {**PROBE, 'pts': clip_pts})

    def test_receipt_boundary_mutations_fail_before_network(self):
        original = json.loads(self.receipt.read_text())
        mutations = [
            {**original, 'clip_sha256': 'b' * 64},
            {**original, 'source_pts': original['source_pts'][:-1]},
            {**original, 'source_pts': [0] * 30},
            {**original, 'source_pts': [True] + original['source_pts'][1:]},
            {**original, 'version': True},
            {**original, 'source_time_base': '0.033333'},
            {**original, 'source_sha256': 'not-a-hash'},
        ]
        duplicates = self.receipt.read_text()[:-1] + ',"clip_sha256":"' + 'b' * 64 + '"}'
        for raw in [json.dumps(value) for value in mutations] + [duplicates]:
            with self.subTest(receipt=raw[-80:]):
                self.receipt.write_text(raw)
                with mock.patch.object(client, 'probe_video', return_value=PROBE):
                    okay, status = client.run(self.args(), resolver=resolver,
                        connection_factory=lambda route: self.fail('must not send'))
                self.assertFalse(okay)
                self.assertEqual(status['error_category'], 'native_receipt_invalid')
                self.assertFalse(self.output.with_suffix('.events.sse').exists())
                self.output.unlink()

    def test_media_mutated_during_probe_is_not_attached(self):
        def change_media(path):
            path.write_bytes(b'another clip of different bytes')
            return PROBE
        with mock.patch.object(client, 'probe_video', side_effect=change_media):
            okay, status = client.run(self.args(), resolver=resolver,
                connection_factory=lambda route: self.fail('must not send'))
        self.assertFalse(okay)
        self.assertEqual(status['error_category'], 'video_preflight_failed')
        self.assertFalse(self.output.with_suffix('.events.sse').exists())

    def test_oversized_or_non_mp4_input_stops_before_probe(self):
        for name, contents in (('short.mp4', b'x' * (client.MAX_BYTES + 1)),
                               ('short.mov', b'fake clip bytes')):
            with self.subTest(name=name):
                self.video = self.workspace / name
                self.video.write_bytes(contents)
                with mock.patch.object(client, 'probe_video') as probe:
                    okay, status = client.run(self.args(), resolver=resolver,
                        connection_factory=lambda route: self.fail('must not send'))
                probe.assert_not_called()
                self.assertFalse(okay)
                self.assertEqual(status['error_category'], 'video_preflight_failed')
                self.output.unlink()

    def test_existing_status_or_stream_is_never_overwritten(self):
        events = self.output.with_suffix('.events.sse')
        for existing in (self.output, events):
            with self.subTest(existing=existing.name):
                existing.write_bytes(b'previous evidence')
                with self.assertRaisesRegex(client.ClientError, 'output_exists'):
                    client.run(self.args(), resolver=resolver,
                        connection_factory=lambda route: self.fail('must not send'))
                self.assertEqual(existing.read_bytes(), b'previous evidence')
                existing.unlink()

    def test_atomic_output_preserves_existing_file_on_failed_publish(self):
        self.output.write_text('existing record')
        with self.assertRaisesRegex(client.ClientError, 'output_write_failed'):
            client._save(self.output, {'state': 'new'}, first=True)
        self.assertEqual(self.output.read_text(), 'existing record')
        self.assertEqual(list(self.workspace.glob('out.json.*.tmp')), [])
        with mock.patch.object(Path, 'replace', side_effect=OSError(SECRET)):
            with self.assertRaisesRegex(client.ClientError, 'output_write_failed'):
                client._save(self.output, {'state': 'later'})
        self.assertEqual(self.output.read_text(), 'existing record')
        self.assertEqual(list(self.workspace.glob('out.json.*.tmp')), [])

    def test_tls_connection_uses_checked_ip_and_pinned_host_for_sni(self):
        wrapped = object()
        fake_socket = mock.Mock()
        fake_context = mock.Mock()
        fake_context.wrap_socket.return_value = wrapped
        route = {'host': HOST, 'port': 443, 'ip': IP, 'key': SECRET}
        with mock.patch.object(client.ssl, 'create_default_context',
                               return_value=fake_context), \
             mock.patch.object(client.socket, 'create_connection',
                               return_value=fake_socket) as connect:
            connection = client.PinnedHTTPSConnection(route)
            connection.connect()
        self.assertEqual(connect.call_args.args[0], (IP, 443))
        fake_context.wrap_socket.assert_called_once_with(fake_socket,
                                                          server_hostname=HOST)
        self.assertIs(connection.sock, wrapped)


if __name__ == '__main__':
    unittest.main()
