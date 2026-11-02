import os,unittest
@unittest.skipUnless(os.environ.get('RUN_LIVE_OLLAMA_TESTS')=='1','opt-in: RUN_LIVE_OLLAMA_TESTS=1 requires installed Ollama; no automatic model downloads')
class LiveOllamaTests(unittest.TestCase):
    def test_local_generation(self):
        import rag_eval as rag
        self.assertEqual(rag.model_identity()['name'],'llama3.1:8b')
        self.assertTrue(rag.invoke_model(rag.get_llm(),'Reply with OK.','Local smoke test.').strip())
@unittest.skipUnless(os.environ.get('RUN_LIVE_RETRIEVAL_TESTS')=='1','opt-in: RUN_LIVE_RETRIEVAL_TESTS=1 requires rebuilt local Chroma and cached embeddings')
class LiveRetrievalTests(unittest.TestCase):
    def test_local_index_retrieves_pdf_pages(self):
        import rag_eval as rag
        hits=rag.retrieve(rag.read_questions()[0]['question'],rag.load_chroma(),'hybrid',4,16)
        self.assertTrue(hits)
        self.assertTrue(all(h['source'].endswith('.pdf') and h['page']>0 for h in hits))
