import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from bls_rag import webui
from bls_rag.generation import ModelCallError
from bls_rag.paths import PDF_DIR

FAKE_ANSWER = {'answer': 'The rate was 4.5 percent [S1].', 'model': 'llama3.1:8b', 'use_documents': True,
               'seconds': 1.0, 'output_tokens': 12,
               'sources': [{'rank': 1, 'source': 'a.pdf', 'page': 9, 'excerpt': 'Washington 4.5'}]}


class ParseAskTests(unittest.TestCase):
    def test_valid_request_is_normalised(self):
        parsed = webui.parse_ask(json.dumps({'question': '  Rate? ', 'model': 'llama3.1:8b',
                                             'use_documents': False, 'retrieval_mode': 'dense'}).encode())
        self.assertEqual(parsed, {'question': 'Rate?', 'model': 'llama3.1:8b',
                                  'use_documents': False, 'retrieval_mode': 'dense'})

    def test_documents_are_used_by_default(self):
        self.assertTrue(webui.parse_ask(b'{"question": "Rate?", "model": "m"}')['use_documents'])

    def test_bad_requests_are_rejected(self):
        for body in (b'not json', b'[]', b'{"question": "  ", "model": "m"}', b'{"question": "Rate?"}',
                     b'{"question": "Rate?", "model": "m", "retrieval_mode": "web"}',
                     json.dumps({'question': 'x' * (webui.MAX_QUESTION_CHARS + 1), 'model': 'm'}).encode()):
            with self.subTest(body=body[:40]), self.assertRaises(webui.RequestError) as caught:
                webui.parse_ask(body)
            self.assertEqual(caught.exception.status, 400)


class ModelListTests(unittest.TestCase):
    @patch('bls_rag.webui.generation.ollama_json')
    def test_embedding_models_are_not_offered(self, ollama_json):
        ollama_json.return_value = {'models': [
            {'name': 'nomic-embed-text:latest', 'details': {'family': 'nomic-bert'}},
            {'name': 'llama3.1:8b', 'details': {'family': 'llama'}},
            {'name': 'llama3.1-bls-ft:latest', 'details': {'family': 'llama'}}]}
        self.assertEqual(webui.chat_models(), ['llama3.1-bls-ft:latest', 'llama3.1:8b'])

    @patch('bls_rag.webui.generation.ollama_json', side_effect=OSError('refused'))
    def test_status_reports_unreachable_ollama(self, _):
        status = webui.status()
        self.assertEqual(status['models'], [])
        self.assertIn('Ollama is not reachable', status['ollama_error'])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = webui.make_server(0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def ask(self, payload, content_type='application/json'):
        status, _, body = self.request('POST', '/api/ask', json.dumps(payload).encode(),
                                       {'Content-Type': content_type})
        return status, json.loads(body)

    def test_page_is_served(self):
        status, content_type, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith('text/html'))
        self.assertIn(b'BLS Labor Market Assistant', body)

    def test_requests_for_other_hosts_are_refused(self):
        status, _, _ = self.request('GET', '/', headers={'Host': 'evil.example'})
        self.assertEqual(status, 403)

    @patch('bls_rag.webui.answer', return_value=FAKE_ANSWER)
    def test_ask_returns_answer_and_sources(self, answer):
        status, data = self.ask({'question': 'Rate?', 'model': 'llama3.1:8b'})
        self.assertEqual(status, 200)
        self.assertEqual(data, FAKE_ANSWER)
        answer.assert_called_once_with(question='Rate?', model='llama3.1:8b', use_documents=True,
                                       retrieval_mode=webui.config()['retrieval_mode'])

    @patch('bls_rag.webui.answer')
    def test_ask_requires_json_and_a_question(self, answer):
        self.assertEqual(self.ask({'question': 'Rate?', 'model': 'm'}, 'text/plain')[0], 415)
        status, data = self.ask({'question': '', 'model': 'm'})
        self.assertEqual((status, data['error']), (400, 'Type a question first.'))
        answer.assert_not_called()

    @patch('bls_rag.webui.answer', side_effect=ModelCallError('deadline_exceeded'))
    def test_model_failures_become_readable_errors(self, _):
        status, data = self.ask({'question': 'Rate?', 'model': 'm'})
        self.assertEqual((status, data['error']), (502, 'The model took too long to answer.'))

    @patch('bls_rag.webui.answer', side_effect=RuntimeError('No index exists. Run: uv run bls-rag ingest'))
    def test_missing_index_is_explained(self, _):
        status, data = self.ask({'question': 'Rate?', 'model': 'm'})
        self.assertEqual(status, 500)
        self.assertIn('bls-rag ingest', data['error'])

    def test_only_corpus_pdfs_are_served(self):
        name = sorted(PDF_DIR.glob('*.pdf'))[0].name
        status, content_type, body = self.request('GET', f'/pdf/{name}')
        self.assertEqual((status, content_type), (200, 'application/pdf'))
        self.assertTrue(body.startswith(b'%PDF'))
        for path in ('/pdf/missing.pdf', '/pdf/..%2F..%2Fpyproject.toml', '/pdf/../../pyproject.toml'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)


if __name__ == '__main__':
    unittest.main()
