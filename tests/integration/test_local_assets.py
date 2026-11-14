import json
import os
import unittest

from bls_rag.paths import RAG_EVAL_DIR


@unittest.skipUnless(os.environ.get('RUN_LIVE_OLLAMA_TESTS') == '1',
                     'opt-in: RUN_LIVE_OLLAMA_TESTS=1 requires installed Ollama; no automatic model downloads')
class LiveOllamaTests(unittest.TestCase):
    def test_local_generation(self):
        from bls_rag import generation
        self.assertEqual(generation.model_identity()['name'], 'llama3.1:8b')
        self.assertTrue(generation.invoke_model(generation.get_llm(), 'Reply with OK.', 'Local smoke test.').strip())


@unittest.skipUnless(os.environ.get('RUN_LIVE_RETRIEVAL_TESTS') == '1',
                     'opt-in: RUN_LIVE_RETRIEVAL_TESTS=1 requires rebuilt local Chroma and cached embeddings')
class LiveRetrievalTests(unittest.TestCase):
    def test_local_index_retrieves_pdf_pages(self):
        from bls_rag import index, retrieval
        question = json.loads((RAG_EVAL_DIR / 'questions.json').read_text(encoding='utf-8'))[0]['question']
        hits = retrieval.retrieve(question, index.load_chroma(), 'hybrid', 4, 16)
        self.assertTrue(hits)
        self.assertTrue(all(h['source'].endswith('.pdf') and h['page'] > 0 for h in hits))
