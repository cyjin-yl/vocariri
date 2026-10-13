"""Offline checks for the R5b prompt/map client; no model or DNS requests."""

import base64
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'remote'))
import video_request_checked_r5b as client


R4_PTS = [0, 528, 1072, 1600, 2128, 2672, 3200, 3744, 4272,
          4800, 5344, 5872, 6400, 6944, 7472, 8000, 8544, 9072]
R4_PROBE = {'width': 1280, 'height': 720, 'duration_seconds': 0.6,
            'decoded_frames': 18, 'time_base': '1/16000', 'pts': R4_PTS}
R4_TIMES = ['0.000', '0.033', '0.067', '0.100', '0.133', '0.167',
            '0.200', '0.234', '0.267', '0.300', '0.334', '0.367',
            '0.400', '0.434', '0.467', '0.500', '0.534', '0.567']


class R5bOfflineTests(unittest.TestCase):
    def test_r4_native_pts_map_is_one_based_and_has_no_nominal_end_frame(self):
        entries = client.decoded_frame_map(R4_PROBE).split(', ')
        self.assertEqual(entries, [f'{i}={time}s'
                                   for i, time in enumerate(R4_TIMES, 1)])
        self.assertEqual(len(entries), 18)
        self.assertNotIn('19=', ', '.join(entries))
        self.assertNotIn('0.600s', ', '.join(entries))

    def test_payload_retains_native_video_and_unlimited_xhigh_thinking(self):
        clip = b'isolated fake MP4 bytes'
        payload, audit = client.build_payload(clip, R4_PROBE)
        self.assertEqual(payload['model'], client.MODEL)
        self.assertEqual(payload['reasoning_effort'], 'xhigh')
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': True})
        for cap in ('max_tokens', 'max_completion_tokens', 'max_output_tokens'):
            self.assertNotIn(cap, payload)
        self.assertEqual(payload['media_io_kwargs']['video']['num_frames'], 18)
        self.assertIs(payload['mm_processor_kwargs']['do_sample_frames'], False)
        self.assertEqual(audit['requested_frames'], 18)
        parts = payload['messages'][0]['content']
        self.assertEqual([part['type'] for part in parts], ['text', 'video_url'])
        self.assertIn('1=0.000s', parts[0]['text'])
        self.assertIn('18=0.567s', parts[0]['text'])
        self.assertNotIn('{frame_map}', parts[0]['text'])
        self.assertIn('SAME identifiable glyph', parts[0]['text'])
        self.assertIn('in_front_of_text/behind_text/undetermined', parts[0]['text'])
        self.assertIn('proposed_implementation', parts[0]['text'])
        encoded = parts[1]['video_url']['url']
        self.assertTrue(encoded.startswith('data:video/mp4;base64,'))
        self.assertEqual(base64.b64decode(encoded.partition(',')[2]), clip)

    def test_count_pts_and_display_precision_mismatches_fail_closed(self):
        cases = [
            {**R4_PROBE, 'decoded_frames': 19},
            {**R4_PROBE, 'pts': R4_PTS[:-1]},
            {**R4_PROBE, 'pts': R4_PTS[:5] + [R4_PTS[4]] + R4_PTS[6:]},
            {**R4_PROBE, 'pts': [True] + R4_PTS[1:]},
            {**R4_PROBE, 'time_base': '0/16000'},
            {**R4_PROBE, 'decoded_frames': 2, 'pts': [0, 1]},
        ]
        for probe in cases:
            with self.subTest(probe=probe):
                with self.assertRaisesRegex(client.ClientError,
                                            '^video_preflight_failed$'):
                    client.build_payload(b'fake clip', probe)

    def test_run_rejects_map_count_mismatch_before_route_or_stream(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / 'workspace'
            workspace.mkdir()
            video = workspace / 'window.mp4'
            video.write_bytes(b'fake clip')
            output = workspace / 'r5b.status.json'
            args = SimpleNamespace(workspace=str(workspace), video=str(video),
                output=str(output), source_id='public-window', start=1.0,
                native_pts_receipt=str(workspace / 'receipt.json'),
                config_path=Path(temp) / 'private-config.yml',
                route_pin=Path(temp) / 'private-pin.json', fresh_cache=False)
            bad_probe = {**R4_PROBE, 'decoded_frames': 19}
            with mock.patch.object(client, 'probe_video', return_value=bad_probe), \
                 mock.patch.object(client, 'validate_native_receipt', return_value={}), \
                 mock.patch.object(client, 'load_route',
                                   side_effect=AssertionError('route must not be read')) as route, \
                 mock.patch.object(client, 'stream_request',
                                   side_effect=AssertionError('must not send')) as stream:
                okay, status = client.run(args)
            self.assertFalse(okay)
            self.assertEqual(status, {'state': 'blocked',
                                      'error_category': 'video_preflight_failed'})
            record = json.loads(output.read_text())
            self.assertEqual(record['state'], 'blocked')
            self.assertEqual(record['client_version'], 'r5b-20260927')
            self.assertFalse(output.with_suffix('.events.sse').exists())
            route.assert_not_called()
            stream.assert_not_called()

    def test_private_pinned_route_remains_fail_closed_with_synthetic_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / 'workspace'
            workspace.mkdir()
            config = root / 'models.yml'
            pin_path = root / 'pin.json'
            host = 'selfhost.example.invalid'
            base = f'https://{host}/v1'
            ip = '100.64.10.23'
            config.write_text(json.dumps({'providers': {client.PROVIDER: {
                'baseUrl': base, 'models': [{'id': client.MODEL}],
                'apiKey': 'SYNTHETIC-TEST-KEY'}}}))
            pin = {'provider': client.PROVIDER, 'model': client.MODEL,
                   'route_kind': 'operator_verified_direct_self_hosted',
                   'base_url': base, 'allowed_ips': [ip]}
            pin_path.write_text(json.dumps(pin))
            if os.name == 'posix':
                config.chmod(0o600)
                pin_path.chmod(0o600)
            resolver = lambda *a, **k: [(None, None, None, None, (ip, 443))]
            route = client.load_route(config, pin_path, workspace,
                                      resolver=resolver)
            self.assertEqual(route['ip'], ip)
            pin['allowed_ips'] = ['8.8.8.8']
            pin_path.write_text(json.dumps(pin))
            with self.assertRaises(client.ClientError):
                client.load_route(config, pin_path, workspace, resolver=resolver)


if __name__ == '__main__':
    unittest.main()
