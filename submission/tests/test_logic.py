import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from rag_eval import fuse_ranked_lists, tokenize, read_questions, invoke_model, response_text
from rag_eval import lexical_tokens, lexical_search, hybrid_selection


class LogicTests(unittest.TestCase):
    def test_lexical_vocabulary_equivalence(self):
        self.assertEqual(lexical_tokens('ESD average yearly wages 2024'),
                         lexical_tokens('Employment Security Department average annual wage 2024'))

    def test_hybrid_keeps_independent_lexical_evidence(self):
        dense = ['shared1', 'shared2', 'shared3', 'dense-only']
        lexical = ['table-with-second-figure', 'shared1', 'shared2', 'shared3']
        self.assertNotIn('table-with-second-figure', fuse_ranked_lists(dense, lexical)[:3])
        selected = hybrid_selection(dense, lexical, 3)
        self.assertIn('table-with-second-figure', selected)
        self.assertEqual(len(set(selected)), 3)
        self.assertEqual(hybrid_selection(dense, [], 3), dense[:3])
        self.assertEqual(hybrid_selection([], [], 4), [])

    def test_model_response_keeps_only_visible_text(self):
        llm = Mock()
        llm.invoke.return_value = SimpleNamespace(content=[
            {'type': 'text', 'text': 'Answer: ', 'extras': {'signature': 'hidden'}},
            {'type': 'thinking', 'text': 'private reasoning'},
            {'type': 'text', 'text': 'hidden thought', 'thought': True},
            {'type': 'image', 'text': 'not answer text'},
            {'type': 'text', 'text': 'supported fact.'},
            {'type': 'text', 'text': None},
        ])
        self.assertEqual(invoke_model(llm, 'system', 'question'), 'Answer: supported fact.')
        self.assertEqual(response_text('plain answer'), 'plain answer')
        self.assertEqual(response_text([{'type': 'signature', 'data': 'hidden'}]), '')
        self.assertEqual(response_text(None), '')

    def test_tokenizer(self):
        self.assertEqual(tokenize('B&O in 2024: WA?'), ['b', 'o', 'in', '2024', 'wa'])

    def test_rrf_first_ranked_in_both(self):
        ranking = fuse_ranked_lists(['a', 'b', 'c'], ['a', 'c', 'd'])
        self.assertEqual(ranking[0], 'a')
        self.assertEqual(len(ranking), 4)

    def test_eval_set(self):
        cases = read_questions()
        self.assertEqual(len(cases), 9)
        self.assertEqual(len(set(c['id'] for c in cases)), 9)


if __name__ == '__main__':
    unittest.main()
