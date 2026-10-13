import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from visual_queue import plan_batches


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'outputs/visual-batches').mkdir(parents=True)

    def sheet(self, source, n):
        p = self.root / 'materials' / source / f'sheet-{n:04}.jpg'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f'{source}:{n}'.encode())
        return p

    def status(self, batch_id, files, state='response_received_unreviewed'):
        out = self.root / 'outputs/visual-batches'
        record = {'id': batch_id, 'state': state, 'files': {
            p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
        (out / (batch_id + '.status.json')).write_text(json.dumps(record))
        if state == 'response_received_unreviewed':
            (out / (batch_id + '.json')).write_text('{"input_observed":true}')

    def test_inserting_earlier_source_does_not_requeue_old_images(self):
        old = [self.sheet('B', n) for n in range(5)]
        self.status('one', old[:3]); self.status('two', old[3:])
        new = self.sheet('A', 0)
        batches, counts = plan_batches(self.root)
        self.assertEqual(batches, [[new]])
        self.assertEqual(counts['pending_sheets'], 1)

    def test_batches_do_not_cross_sources_and_changed_bytes_are_pending(self):
        a = self.sheet('A', 0); b = self.sheet('B', 0)
        self.status('one', [a]); a.write_bytes(b'new pixels')
        batches, _ = plan_batches(self.root)
        self.assertEqual(batches, [[a], [b]])

    def test_unfinished_request_cannot_be_evaded_by_regrouping(self):
        files = [self.sheet('B', n) for n in range(2)]
        self.status('one', files, 'requesting'); self.sheet('A', 0)
        with self.assertRaisesRegex(ValueError, 'Reconcile'):
            plan_batches(self.root)

    def test_duplicate_history_is_retained_but_not_requeued(self):
        f = self.sheet('B', 0)
        self.status('one', [f]); self.status('two', [f])
        batches, counts = plan_batches(self.root)
        self.assertEqual(batches, [])
        self.assertEqual(counts['repeated_completed_sheet_appearances'], 1)


if __name__ == '__main__':
    unittest.main()
