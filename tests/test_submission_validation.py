import tempfile
import unittest
from pathlib import Path
from verify_submission import check_hashes, safe_path, sha256, verify_package, ROOT

class SubmissionValidationTests(unittest.TestCase):
    def test_published_package_validates_offline(self):
        self.assertEqual(verify_package(ROOT)['paired_cases'],9)

    def test_missing_assets_are_explicit_but_missing_results_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(check_hashes(root,{'index/chunks.jsonl':'unused'})[1],['index/chunks.jsonl'])
            with self.assertRaises(ValueError):
                check_hashes(root,{'index/chunks.jsonl':'unused'},require_assets=True)
            with self.assertRaises(ValueError):
                check_hashes(root,{'docs/source.pdf':'unused'})
            with self.assertRaises(ValueError):
                check_hashes(root,{'final_artifacts/result.json':'unused'})

    def test_tampered_existing_asset_is_never_silently_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'docs').mkdir()
            path=root/'docs/source.pdf'; path.write_bytes(b'original')
            expected=sha256(path); path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                check_hashes(root,{'docs/source.pdf':expected})

    def test_manifest_path_cannot_escape_package(self):
        for name in ['../private','/private','C:/private','docs/../../private','docs\\private']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_path(ROOT,name)
