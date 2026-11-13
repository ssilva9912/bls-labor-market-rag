import io
import json
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bls_rag import worker as model_worker
from bls_rag.config import config
from bls_rag.generation import BoundedChatModel, ModelCallError


class GenerationTests(unittest.TestCase):
    def test_legacy_provider_settings_cannot_enable_hosted_generation(self):
        with patch.dict(os.environ, {'PROVIDER': 'gemini', 'CHAT_MODEL': 'gemini-old'}, clear=True):
            self.assertEqual(config()['provider'], 'ollama')
            self.assertEqual(config()['chat_model'], 'llama3.1:8b')

    def test_errors_withhold_server_details(self):
        exc = RuntimeError('private server details')
        payload = model_worker.safe_error_payload(exc)
        self.assertEqual(payload['error_category'], 'ollama_failure')
        self.assertNotIn('private', json.dumps(payload))

    @patch('bls_rag.generation.subprocess.run')
    def test_deadline_is_a_failure_not_an_answer(self, run):
        run.side_effect = subprocess.TimeoutExpired('worker', 240, stderr='private server details')
        model = BoundedChatModel()
        with self.assertRaises(ModelCallError) as caught:
            model.invoke([('human', 'question')])
        self.assertEqual(caught.exception.category, 'deadline_exceeded')
        self.assertNotIn('private', str(caught.exception))
        self.assertEqual(model.last_call['status'], 'failed')

    @patch('bls_rag.generation.subprocess.run')
    def test_worker_start_failure_is_recorded_separately(self, run):
        run.side_effect = OSError('local private path')
        model = BoundedChatModel()
        with self.assertRaises(ModelCallError) as caught:
            model.invoke([])
        self.assertEqual(caught.exception.category, 'worker_start_failure')
        self.assertEqual(model.last_call['status'], 'failed')
        self.assertNotIn('private', str(caught.exception))

    @patch('bls_rag.generation.subprocess.run')
    def test_success_keeps_answer_and_timing_separate(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(
            {'answer': 'Clean answer', 'finish_reason': 'stop',
             'ollama_metrics': {'eval_count': 3, 'eval_duration': 1000000}}))
        model = BoundedChatModel()
        self.assertEqual(model.invoke([]).content, 'Clean answer')
        self.assertEqual(model.last_call['ollama_metrics']['eval_count'], 3)
        self.assertEqual(model.last_call['status'], 'completed')
        self.assertIn('elapsed_seconds', model.last_call)

    @patch('bls_rag.worker.generation.create_ollama_llm')
    def test_native_ollama_length_stop_is_not_a_completed_answer(self, create):
        create.return_value.invoke.return_value = SimpleNamespace(
            content='incomplete text', response_metadata={'done_reason': 'length',
                                                         'signature': 'hidden'})
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO('{"messages": []}')), patch('sys.stdout', output):
            model_worker.main()
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['error_category'], 'truncated_response')
        self.assertNotIn('answer', payload)
        self.assertNotIn('signature', output.getvalue())
