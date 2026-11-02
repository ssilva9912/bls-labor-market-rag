import copy
import json
import unittest
from score_final import OUT, validate

class FinalScoringTests(unittest.TestCase):
    def setUp(self):
        self.rows = [json.loads(x) for x in (OUT/'final_evaluation.jsonl').read_text(encoding='utf-8').splitlines()]
        self.judgments = json.loads((OUT/'scoring_judgments.json').read_text(encoding='utf-8'))

    def test_recorded_judgments_cover_actual_final_contexts(self):
        validate(self.rows, self.judgments)

    def test_changed_outputs_cannot_inherit_manual_scores(self):
        bad = copy.deepcopy(self.judgments)
        bad['raw_sha256'] = 'changed'
        with self.assertRaises(AssertionError):
            validate(self.rows, bad)

    def test_runtime_failure_cannot_be_counted_as_wrong_answer(self):
        bad = copy.deepcopy(self.rows)
        bad[0]['rag_error'] = {'category':'deadline_exceeded'}
        with self.assertRaises(AssertionError):
            validate(bad, self.judgments)
