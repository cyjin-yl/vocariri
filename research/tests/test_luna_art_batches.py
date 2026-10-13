import importlib.util
from pathlib import Path
import unittest

p = Path(__file__).resolve().parents[1] / 'remote/luna_art_batches.py'
spec = importlib.util.spec_from_file_location('art', p)
art = importlib.util.module_from_spec(spec)
spec.loader.exec_module(art)


class ArtEvidenceTests(unittest.TestCase):
    def check(self, citations, source='source', url='https://example.test/source'):
        pattern = {'source_id': source, 'source_url': url, 'evidence_files': citations}
        art.validate_patterns({'art_patterns': [pattern]},
                              {'source_id': 'source', 'source_url': 'https://example.test/source'},
                              {'frame.png': 'digest'})

    def test_structured_citation_preserves_annotations(self):
        citation = {'file': 'frame.png', 'timestamp': 12, 'observation': 'outline'}
        self.check([citation])
        self.assertEqual(citation['observation'], 'outline')

    def test_string_citation(self):
        self.check(['frame.png'])

    def test_unattached_or_malformed_citations_rejected(self):
        for citation in ['other.png', {'file': 'other.png'}, {'timestamp': 12}, {'file': []}, 4]:
            with self.subTest(citation=citation), self.assertRaises(ValueError):
                self.check([citation])

    def test_empty_citations_rejected(self):
        with self.assertRaises(ValueError):
            self.check([])

    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):
            self.check(['frame.png'], source='wrong')
        with self.assertRaises(ValueError):
            self.check(['frame.png'], url='https://example.test/wrong')

    def test_stream_prefix_and_grounding(self):
        obj = art.parse_response('Working...\n{"input_observed":true,"art_patterns":[],"unknowns":[]}')
        self.assertEqual(obj['art_patterns'], [])
        with self.assertRaises(ValueError):
            art.parse_response('{"input_observed":false,"art_patterns":[],"unknowns":[]}')

    def test_labeled_frame_inventory_is_mandatory(self):
        batch = {'full_frame_samples': [{'labeled_file': 'frame.png'}]}
        for frames in [None, [], [{'file': 'other.png'}], [{'file': 'frame.png'}, {'file': 'frame.png'}]]:
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                art.validate_patterns({'frame_observations': frames, 'art_patterns': []}, batch, {'frame.png': 'hash'})
        art.validate_patterns({'frame_observations': [{'file': 'frame.png'}], 'art_patterns': []}, batch, {'frame.png': 'hash'})


if __name__ == '__main__':
    unittest.main()
