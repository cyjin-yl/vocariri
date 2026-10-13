"""Cross-platform FFmpeg showinfo fallback checks; offline only."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'remote'))
import video_request_checked_r5c as client

PTS = [0, 533, 1067, 1600, 2133, 2667, 3200, 3733, 4267, 4800,
       5333, 5867, 6400, 6933, 7467, 8000, 8533, 9067, 9600, 10133,
       10667, 11200, 11733, 12267, 12800, 13333, 13867, 14400,
       14933, 15467, 16000, 16533, 17067, 17600, 18133, 18667]


def fallback_output(address='000001B882201540'):
    prefix = f'[Parsed_showinfo_0 @ {address}]'
    rows = ['  Duration: 00:00:01.20, start: 0.000000, bitrate: 1200 kb/s',
            f'{prefix} config in time_base: 1/16000, frame_rate: 30/1']
    rows += [f'{prefix} n: {i} pts: {pts} pts_time:{pts / 16000:.6f} '
             'fmt:yuv420p s:1280x720 i:P'
             for i, pts in enumerate(PTS)]
    return SimpleNamespace(stderr=('\n'.join(rows) + '\n').encode(),
                           stdout=b'frame=36\nprogress=end\n')


class FallbackAddressTests(unittest.TestCase):
    def decode(self, output):
        with mock.patch.object(client, '_ffmpeg_executable', return_value='offline-ffmpeg'), \
             mock.patch.object(client.subprocess, 'run', return_value=output):
            return client._probe_ffmpeg_showinfo(Path('retained.mp4'))

    def test_windows_bare_hex_and_linux_prefixed_hex_preserve_all_native_pts(self):
        for address in ('000001B882201540', '0x7fabc01234', 'ABC123', '0xABC123'):
            with self.subTest(address=address):
                width, height, duration, timebase, pts = self.decode(fallback_output(address))
                self.assertEqual((width, height, duration, timebase),
                                 (1280, 720, 1.2, '1/16000'))
                self.assertEqual(pts, PTS)

    def test_actual_probe_fallback_when_ffprobe_is_missing(self):
        def run(args, **kwargs):
            if args[0] == 'ffprobe':
                raise FileNotFoundError('offline fixture: ffprobe absent')
            return fallback_output()
        with mock.patch.object(client, '_ffmpeg_executable', return_value='offline-ffmpeg'), \
             mock.patch.object(client.subprocess, 'run', side_effect=run):
            probe = client.probe_video(Path('retained.mp4'))
        self.assertEqual(probe['pts'], PTS)
        self.assertEqual(probe['decoded_frames'], 36)
        self.assertEqual(probe['time_base'], '1/16000')

    def test_invalid_address_does_not_accept_any_frames(self):
        for address in ('', '0x', 'ZZ0123', '1234 trailing'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.decode(fallback_output(address))

    def test_two_showinfo_instances_remain_rejected(self):
        output = fallback_output()
        output.stderr = output.stderr.replace(
            b'[Parsed_showinfo_0 @ 000001B882201540] n: 20',
            b'[Parsed_showinfo_0 @ 000001B882201541] n: 20')
        with self.assertRaisesRegex(ValueError, 'mixed showinfo filters'):
            self.decode(output)

    def test_incomplete_native_frame_sequence_remains_rejected(self):
        output = fallback_output()
        output.stderr = b'\n'.join(line for line in output.stderr.splitlines()
                                   if b'] n: 17 ' not in line)
        with self.assertRaises(ValueError):
            self.decode(output)

    def test_progress_count_disagreement_remains_rejected(self):
        output = fallback_output()
        output.stdout = b'frame=35\nprogress=end\n'
        with self.assertRaises(ValueError):
            self.decode(output)

    def test_reasoning_and_native_video_policy_unchanged(self):
        probe = {'width': 1280, 'height': 720, 'duration_seconds': 1.2,
                 'decoded_frames': 36, 'time_base': '1/16000', 'pts': PTS}
        payload, audit = client.build_payload(b'offline video fixture', probe)
        self.assertEqual(payload['reasoning_effort'], 'xhigh')
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': True})
        self.assertEqual(payload['media_io_kwargs']['video']['num_frames'], 36)
        self.assertFalse(payload['mm_processor_kwargs']['do_sample_frames'])
        for key in ('max_tokens', 'max_completion_tokens', 'max_output_tokens'):
            self.assertNotIn(key, payload)
        self.assertEqual(audit['requested_frames'], 36)
        self.assertEqual(client.CLIENT_VERSION, 'r5c-20261001')


if __name__ == '__main__':
    unittest.main()
