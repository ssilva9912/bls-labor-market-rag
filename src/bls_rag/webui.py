"""Local web UI: ``uv run bls-rag ui``.

A small standard-library HTTP server bound to localhost. It serves one page
(``webui.html``) and a JSON API that answers a question with the same
retrieval, prompts and bounded generation as ``bls-rag ask``.
"""
from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from bls_rag import generation
from bls_rag.config import config
from bls_rag.paths import INDEX_DIR, PDF_DIR

PAGE = Path(__file__).with_name('webui.html')
MAX_QUESTION_CHARS = 2000
MAX_BODY_BYTES = 16_384

_generation_lock = threading.Lock()  # one local GPU: answer one question at a time
_store = None


class RequestError(Exception):
    """A problem to show the user, with its HTTP status."""
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


def chat_models() -> list[str]:
    """Installed Ollama models that can chat (embedding models are left out)."""
    models = generation.ollama_json('/api/tags')['models']
    return sorted(m['name'] for m in models
                  if 'embed' not in m['name'] and 'bert' not in m.get('details', {}).get('family', ''))


def status() -> dict:
    settings = config()
    try:
        models, ollama_error = chat_models(), None
    except (OSError, ValueError, KeyError):
        models, ollama_error = [], f'Ollama is not reachable at {settings["ollama_base_url"]}. Start Ollama and reload.'
    default = settings['chat_model']
    if default not in models:
        default = next((m for m in models if m == f'{default}:latest'), models[0] if models else default)
    return {'models': models, 'default_model': default, 'ollama_error': ollama_error,
            'index_ready': (INDEX_DIR / 'manifest.json').exists(),
            'retrieval_mode': settings['retrieval_mode'],
            'documents': sorted(p.name for p in PDF_DIR.glob('*.pdf'))}


def _load_store():
    global _store
    if _store is None:
        from bls_rag import index
        _store = index.load_chroma()
    return _store


def answer(question: str, model: str, use_documents: bool, retrieval_mode: str) -> dict:
    """Answer one question; the same code path as ``bls-rag ask``."""
    from bls_rag import retrieval
    settings = config(chat_model=model)
    generation.model_identity(settings)  # refuses models that are not installed
    llm = generation.get_llm(settings)
    started = time.monotonic()
    with _generation_lock:
        chunks = []
        if use_documents:
            chunks = retrieval.retrieve(question, _load_store(), retrieval_mode,
                                        settings['top_k'], settings['candidate_k'])
            text = generation.answer_rag(llm, question, chunks)
        else:
            text = generation.answer_baseline(llm, question)
    metrics = (llm.last_call or {}).get('ollama_metrics', {})
    return {'answer': text, 'model': model, 'use_documents': use_documents,
            'seconds': round(time.monotonic() - started, 1),
            'output_tokens': metrics.get('eval_count'),
            'sources': [{'rank': c['rank'], 'source': c['source'], 'page': c['page'], 'excerpt': c['content']}
                        for c in chunks]}


def parse_ask(body: bytes) -> dict:
    """Validate an /api/ask request body into keyword arguments for :func:`answer`."""
    try:
        data = json.loads(body)
    except ValueError:
        raise RequestError(400, 'The request was not valid JSON.') from None
    if not isinstance(data, dict):
        raise RequestError(400, 'The request was not valid JSON.')
    question = data.get('question')
    if not isinstance(question, str) or not question.strip():
        raise RequestError(400, 'Type a question first.')
    if len(question) > MAX_QUESTION_CHARS:
        raise RequestError(400, f'Questions are limited to {MAX_QUESTION_CHARS} characters.')
    model = data.get('model')
    if not isinstance(model, str) or not model.strip():
        raise RequestError(400, 'Choose a model.')
    mode = data.get('retrieval_mode', config()['retrieval_mode'])
    if mode not in ('hybrid', 'dense'):
        raise RequestError(400, 'Retrieval mode must be "hybrid" or "dense".')
    return {'question': question.strip(), 'model': model.strip(),
            'use_documents': data.get('use_documents', True) is not False, 'retrieval_mode': mode}


class Handler(BaseHTTPRequestHandler):
    server_version = 'bls-rag-ui'

    def log_message(self, format, *args):  # keep the terminal quiet
        pass

    def _send(self, status_code: int, body: bytes, content_type: str) -> None:
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status_code: int, payload: dict) -> None:
        self._send(status_code, json.dumps(payload, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def _local_request(self) -> bool:
        """Only answer requests addressed to this machine (blocks DNS-rebinding pages)."""
        host = self.headers.get('Host', '').rsplit(':', 1)[0].strip('[]')
        if host in ('127.0.0.1', 'localhost', '::1'):
            return True
        self._json(403, {'error': 'This UI only answers requests to localhost.'})
        return False

    def do_GET(self):
        if not self._local_request():
            return
        path = self.path.split('?', 1)[0]
        if path == '/':
            self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
        elif path == '/api/status':
            self._json(200, status())
        elif path.startswith('/pdf/'):
            name = unquote(path.removeprefix('/pdf/'))
            match = next((p for p in PDF_DIR.glob('*.pdf') if p.name == name), None)  # corpus files only
            if match is None:
                self._json(404, {'error': 'No such document.'})
            else:
                self._send(200, match.read_bytes(), 'application/pdf')
        else:
            self._json(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self._local_request():
            return
        if self.path != '/api/ask':
            self._json(404, {'error': 'Not found.'})
            return
        try:
            # Requiring JSON keeps other websites from submitting forms to this server.
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise RequestError(415, 'Send JSON.')
            length = int(self.headers.get('Content-Length') or 0)
            if not 0 < length <= MAX_BODY_BYTES:
                raise RequestError(413, 'The request is empty or too large.')
            self._json(200, answer(**parse_ask(self.rfile.read(length))))
        except RequestError as exc:
            self._json(exc.status, {'error': str(exc)})
        except generation.ModelCallError as exc:
            hints = {'deadline_exceeded': 'The model took too long to answer.',
                     'connection_failure': 'Ollama is not reachable. Start Ollama and try again.',
                     'truncated_response': 'The answer was cut off at the output limit.'}
            self._json(502, {'error': hints.get(exc.category, f'The model call failed ({exc.category}).')})
        except (RuntimeError, ValueError, OSError) as exc:
            self._json(500, {'error': str(exc)})


def make_server(port: int = 8000) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def serve(port: int = 8000, open_browser: bool = True) -> None:
    server = make_server(port)
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'BLS RAG UI running at {url}  (Ctrl+C to stop)')
    if open_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()
