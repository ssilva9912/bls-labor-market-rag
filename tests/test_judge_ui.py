import hashlib
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from bls_rag import webui
from bls_rag.evaluation import judge_ui
from bls_rag.generation import ABSTENTION

ARMS = {'base_rag': True, 'ft_rag': True, 'base_closed_book': False}


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    """One answerable and one unanswerable question, three arms, an empty judgments template."""
    def row(case, question, answers):
        return {'id': case, 'question': question, 'retrieved_chunks': [
            {'rank': 1, 'chunk_id': 'x:p9', 'source': 'a.pdf', 'page': 9, 'content': 'Washington 4.5'},
            {'rank': 2, 'chunk_id': 'x:p2', 'source': 'a.pdf', 'page': 2, 'content': 'Other text'}],
            'arms': {name: {'model': 'ft' if name.startswith('ft') else 'base', 'retrieval': retrieval,
                            'answer': answers.get(name), 'error': None if name in answers else {'category': 'deadline'},
                            'call': {}} for name, retrieval in ARMS.items()}}
    raw, judgments, references = root / 'outputs.jsonl', root / 'judgments.json', root / 'references.json'
    rows = [row('B1', 'Rate?', {'base_rag': ABSTENTION, 'ft_rag': '4.5 percent [S2].', 'base_closed_book': 'Unknown.'}),
            row('B9', 'Tax?', {'base_rag': ABSTENTION, 'ft_rag': ABSTENTION + '\n\nSources: None'})]
    raw.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    references.write_text(json.dumps([
        {'id': 'B1', 'answerability': 'answerable', 'reference_answer': '4.5%', 'required_criteria': ['4.5%'],
         'evidence': [{'filename': 'a.pdf', 'pdf_page': 9, 'supporting_excerpt': 'Washington 4.5'}]},
        {'id': 'B9', 'answerability': 'unanswerable-in-corpus', 'reference_answer': ABSTENTION,
         'required_criteria': ['Abstain'], 'evidence': []}]), encoding='utf-8')
    cases = {r['id']: {name: {'correctness': None, 'reason': '', 'abstention': None,
                              **({'citation_support': None} if retrieval else {})}
                       for name, retrieval in ARMS.items()} for r in rows}
    judgments.write_text(json.dumps({'method': 'manual', 'raw_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
                                     'cases': cases}, indent=2) + '\n', encoding='utf-8')
    return raw, judgments, references


class StoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.raw, self.judgments, self.references = write_fixture(Path(directory.name))
        self.store = judge_ui.Store(self.raw, self.judgments, self.references)

    def test_data_joins_outputs_references_and_passages(self):
        data = self.store.data()
        case = data['cases'][0]
        self.assertTrue(case['answerable'])
        self.assertEqual([p['reference'] for p in case['passages']], [True, False])
        self.assertTrue(case['answers']['base_rag']['exact_abstention'])
        self.assertFalse(data['cases'][1]['answerable'])
        self.assertEqual(data['progress'], {'graded': 0, 'total': 5})  # the failed call is not gradable

    def test_save_writes_the_scoring_format_and_counts_progress(self):
        result = self.store.save({'id': 'B1', 'arm': 'ft_rag', 'correctness': 2, 'abstention': False,
                                  'citation_support': 0, 'reason': ' Right value, wrong page. '})
        self.assertEqual(result['progress'], {'graded': 1, 'total': 5})
        saved = json.loads(self.judgments.read_text(encoding='utf-8'))
        self.assertEqual(saved['cases']['B1']['ft_rag'], {'correctness': 2, 'reason': 'Right value, wrong page.',
                                                         'abstention': False, 'citation_support': 0})
        self.assertEqual(saved['method'], 'manual')
        self.assertEqual(saved['raw_sha256'], hashlib.sha256(self.raw.read_bytes()).hexdigest())
        self.assertNotIn('citation_support', saved['cases']['B1']['base_closed_book'])
        self.assertFalse(self.judgments.with_name('judgments.json.tmp').exists())

    def test_completeness_follows_the_rubric(self):
        graded = {'correctness': 0, 'abstention': True, 'reason': 'Abstained.', 'citation_support': None}
        self.assertTrue(judge_ui.complete(graded, retrieval=True))  # citation support is N/A for an abstention
        self.assertFalse(judge_ui.complete({**graded, 'abstention': False}, retrieval=True))
        self.assertTrue(judge_ui.complete({**graded, 'abstention': False}, retrieval=False))
        self.assertFalse(judge_ui.complete({**graded, 'reason': ' '}, retrieval=True))
        self.assertFalse(judge_ui.complete({**graded, 'correctness': None}, retrieval=True))

    def test_invalid_judgments_are_rejected_and_not_written(self):
        before = self.judgments.read_bytes()
        for payload in ({'id': 'B7', 'arm': 'ft_rag'}, {'id': 'B1', 'arm': 'other'},
                        {'id': 'B1', 'arm': 'ft_rag', 'correctness': 3},
                        {'id': 'B1', 'arm': 'ft_rag', 'correctness': True},
                        {'id': 'B1', 'arm': 'ft_rag', 'abstention': 'yes'},
                        {'id': 'B1', 'arm': 'ft_rag', 'citation_support': 2},
                        {'id': 'B1', 'arm': 'ft_rag', 'reason': 'x' * (judge_ui.MAX_REASON_CHARS + 1)}):
            with self.subTest(payload=str(payload)[:60]), self.assertRaises(webui.RequestError):
                self.store.save(payload)
        self.assertEqual(self.judgments.read_bytes(), before)

    def test_judgments_for_other_outputs_are_refused(self):
        self.raw.write_text(self.raw.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            judge_ui.Store(self.raw, self.judgments, self.references)

    def test_second_grader_file_is_offered_as_suggestions(self):
        self.assertIsNone(self.store.data()['suggestions'])
        second = self.judgments.with_name('second.json')
        graded = json.loads(self.judgments.read_text(encoding='utf-8'))
        graded['method'] = 'second grader'
        graded['cases']['B1']['ft_rag'] = {'correctness': 2, 'reason': 'Right.', 'abstention': False, 'citation_support': 0}
        second.write_text(json.dumps(graded), encoding='utf-8')
        data = judge_ui.Store(self.raw, self.judgments, self.references, suggestions=second).data()
        self.assertEqual(data['suggestions']['B1']['ft_rag']['correctness'], 2)
        self.assertEqual(data['suggestions_method'], 'second grader')
        self.assertIsNone(data['judgments']['B1']['ft_rag']['correctness'])  # suggestions never become judgments
        # The judgments file itself is never treated as its own second grader.
        self.assertIsNone(judge_ui.Store(self.raw, self.judgments, self.references, suggestions=self.judgments).data()['suggestions'])
        graded['raw_sha256'] = 'other'
        second.write_text(json.dumps(graded), encoding='utf-8')
        with self.assertRaises(RuntimeError):
            judge_ui.Store(self.raw, self.judgments, self.references, suggestions=second)

    def test_summary_refuses_a_copy_of_the_judgments_file(self):
        with self.assertRaises(webui.RequestError) as caught:
            self.store.summary()
        self.assertEqual(caught.exception.status, 409)


class ServerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.raw, self.judgments, references = write_fixture(Path(directory.name))
        self.server = judge_ui.make_server(judge_ui.Store(self.raw, self.judgments, references), 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, payload=None, headers=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        try:
            body = json.dumps(payload).encode() if payload is not None else None
            connection.request(method, path, body=body,
                               headers=headers or ({'Content-Type': 'application/json'} if body else {}))
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_page_and_data_are_served(self):
        status, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Experiment 02 grading', body)
        status, body = self.request('GET', '/api/data')
        self.assertEqual(status, 200)
        self.assertEqual([c['id'] for c in json.loads(body)['cases']], ['B1', 'B9'])

    def test_judgment_round_trip(self):
        status, body = self.request('POST', '/api/judgment', {'id': 'B9', 'arm': 'base_rag', 'correctness': 2,
                                                              'abstention': True, 'reason': 'Abstained.'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['progress']['graded'], 1)
        self.assertEqual(json.loads(self.judgments.read_text(encoding='utf-8'))['cases']['B9']['base_rag']['correctness'], 2)

    def test_bad_requests_are_refused(self):
        self.assertEqual(self.request('POST', '/api/judgment', {'id': 'B1', 'arm': 'ft_rag', 'correctness': 5})[0], 400)
        self.assertEqual(self.request('POST', '/api/judgment', {'id': 'B1'}, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('POST', '/api/summary', {})[0], 409)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('GET', '/api/status')[0], 404)


if __name__ == '__main__':
    unittest.main()
