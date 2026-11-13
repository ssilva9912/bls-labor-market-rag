import unittest

from bls_rag.retrieval import compact_layout, expanded_query, lexical_search, lexical_tokens, page_matches_measure


class FinalRetrievalTests(unittest.TestCase):
    def test_single_source_bm25_returns_matching_page_despite_negative_idf(self):
        record = {'content': '2024 statewide unemployment annual rate'}
        self.assertEqual(lexical_search('2024 annual unemployment', [record], 4), [record])

    def test_table_column_order_and_values_survive_compaction(self):
        text = 'Rate type       2023       2024\nStatewide rate  4.2%       4.5%\n'
        self.assertEqual(compact_layout(text),
                         'Rate type | 2023 | 2024\nStatewide rate: 2023=4.2%; 2024=4.5%')

    def test_explicit_release_name_filters_other_releases(self):
        record = {'content': 'Statewide rates', 'metadata': {'source': '02_bls_state_employment.pdf'}}
        self.assertFalse(page_matches_measure('Regional and State Unemployment annual averages?', record))

    def test_wide_table_keeps_named_row_and_headers(self):
        from bls_rag.retrieval import page_excerpt
        text='Table 1 unemployment\nYear 2023 2024\n'+'Other state 1 2\n'*500+'Washington 4.2 4.5\np Preliminary'
        excerpt=page_excerpt(text,'Washington unemployment?',1500)
        self.assertIn('Washington 4.2 4.5',excerpt)
        self.assertIn('Table 1',excerpt)
        self.assertIn('p Preliminary',excerpt)

    def test_query_contains_no_reference_answer_injection(self):
        query='Washington annual unemployment?'
        self.assertEqual(expanded_query(query),query)

    def test_source_acronym_is_not_a_topic_signal(self):
        self.assertEqual(lexical_tokens('ESD average wages'), ['average', 'wage'])
