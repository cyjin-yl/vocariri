"""Real decoder checks for fractional FPS, sparse VFR and shifted source PTS."""
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'remote'))
from source_frame_sampler import sample_frames, parse_showinfo, digest


class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import imageio_ffmpeg
        cls.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    def check_clip(self, rate, filters=None, shifted=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'test.mkv'
            args = [self.ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    f'testsrc2=size=96x64:rate={rate}:duration=1.2']
            if filters:
                args += ['-vf', filters, '-fps_mode', 'passthrough']
            subprocess.run(args + ['-c:v', 'ffv1', str(source)], check=True)
            out = root / 'samples'
            result = sample_frames(source, out, self.ffmpeg, width=96)
            # Decode every source frame independently and prove selection is a
            # subset of actual timestamps, with exact pixel/JPEG correspondence.
            native = root / 'native'
            native.mkdir()
            p = subprocess.run([self.ffmpeg, '-hide_banner', '-copyts', '-i',
                                str(source), '-vf', 'scale=96:-2,showinfo',
                                '-fps_mode', 'passthrough', '-q:v', '3',
                                str(native / 'f-%06d.jpg')], capture_output=True,
                               text=True, check=True)
            tb, rows = parse_showinfo(p.stderr)
            by_time = {pts * tb: native / f'f-{n+1:06d}.jpg' for n, pts in rows}
            selected_times = [x['source_pts'] * Fraction(result['time_base'])
                              for x in result['frames']]
            for row, instant in zip(result['frames'], selected_times):
                self.assertIn(instant, by_time)
                self.assertEqual(row['sha256'], digest(by_time[instant]))
            # Independent rational-time expectation: first actual frame per bin.
            expected = {}
            for instant in by_time:
                expected.setdefault(instant * 4 // 1, instant)
            self.assertEqual(selected_times, list(expected.values()))
            self.assertEqual(json.loads((out / 'source-frames.json').read_text()), result)
            if shifted:
                self.assertGreaterEqual(selected_times[0], 5)
                self.assertIsNone(result['playback_origin_seconds'])
            before = (out / 'source-frames.json').read_bytes()
            with self.assertRaises(FileExistsError):
                sample_frames(source, out, self.ffmpeg, width=96)
            self.assertEqual((out / 'source-frames.json').read_bytes(), before)

    def test_fractional_fps(self):
        self.check_clip('30000/1001')

    def test_sparse_variable_rate(self):
        self.check_clip('30', "select='eq(n,0)+eq(n,3)+eq(n,17)+eq(n,29)'")

    def test_nonzero_source_origin(self):
        self.check_clip('30', 'setpts=PTS+5/TB', shifted=True)

    def test_incomplete_mapping_rejected(self):
        with self.assertRaises(ValueError):
            parse_showinfo('config in time_base: 1/30\nn: 1 pts: 1 pts_time: 0.033')


if __name__ == '__main__':
    unittest.main()
