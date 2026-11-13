import tempfile
import unittest
from pathlib import Path

from bls_rag.evaluation.verify import check_hashes, safe_path, sha256, verify_experiment
from bls_rag.paths import LEGACY_RUNTIME_FILES, ROOT, legacy_path


class ExperimentVerificationTests(unittest.TestCase):
    def test_frozen_experiment_validates_offline_in_new_layout(self):
        result = verify_experiment()
        self.assertEqual(result['paired_cases'], 9)
        self.assertEqual(set(result['runtime_code_verified_at_tag']['files']), LEGACY_RUNTIME_FILES)

    def test_legacy_paths_map_to_new_layout(self):
        self.assertEqual(legacy_path('docs/source_inventory.json'), ROOT / 'corpus/source_inventory.json')
        self.assertEqual(legacy_path('docs/a.pdf'), ROOT / 'corpus/pdfs/a.pdf')
        self.assertEqual(legacy_path('questions.json'), ROOT / 'experiments/01_rag_eval/questions.json')
        self.assertIsNone(legacy_path('rag_eval.py'))

    def test_missing_assets_are_explicit_but_missing_results_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(check_hashes(root, {'index/chunks.jsonl': 'unused'})[1], ['index/chunks.jsonl'])
            with self.assertRaises(ValueError):
                check_hashes(root, {'index/chunks.jsonl': 'unused'}, require_assets=True)
            with self.assertRaises(ValueError):
                check_hashes(root, {'docs/source.pdf': 'unused'})

    def test_tampered_existing_asset_is_never_silently_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'docs').mkdir()
            path = root / 'docs/source.pdf'
            path.write_bytes(b'original')
            expected = sha256(path)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                check_hashes(root, {'docs/source.pdf': expected})

    def test_manifest_path_cannot_escape_package(self):
        for name in ['../private', '/private', 'C:/private', 'docs/../../private', 'docs\\private']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_path(ROOT, name)
