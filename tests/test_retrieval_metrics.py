import unittest
from evaluation.score_final import retrieval_metrics
class RetrievalMetricTests(unittest.TestCase):
    def test_page_precision_and_nonexhaustive_reference_recall_are_distinct(self):
        row={'retrieved_chunks':[{'source':'a.pdf','page':2},{'source':'a.pdf','page':3}]}
        judgments={'passages':[{'grade':2},{'grade':1}],'sufficiency':0}
        reference={'evidence':[{'filename':'a.pdf','pdf_page':2},{'filename':'a.pdf','pdf_page':4}]}
        result=retrieval_metrics(row,judgments,reference)
        self.assertEqual(result['precision_at_4'],0.25)
        self.assertEqual(result['reference_evidence_recall_at_4'],0.5)
        self.assertEqual(result['returned'],2)
    def test_unanswerable_reference_recall_is_not_zero(self):
        result=retrieval_metrics({'retrieved_chunks':[]},{'passages':[],'sufficiency':None},{'evidence':[]})
        self.assertIsNone(result['reference_evidence_recall_at_4'])
