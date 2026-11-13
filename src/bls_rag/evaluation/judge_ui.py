"""Grading page for experiment 02: ``uv run python -m bls_rag.evaluation.judge_ui``.

Shows each held-out question with its reference answer, required criteria and
the retrieved pages next to the four answers, and writes the manual judgments
to ``artifacts/judgments.json`` in the format ``finetune_scoring summary``
reads. Judging stays manual; the page only removes the JSON editing and the
hunting for passages. Arms are hidden and shuffled by default (blind grading).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from bls_rag import webui
from bls_rag.evaluation import finetune_scoring as scoring
from bls_rag.generation import ABSTENTION
from bls_rag.paths import RAG_EVAL_DIR

PAGE = Path(__file__).with_name('judge_ui.html')
REFERENCES = RAG_EVAL_DIR / 'references.json'
MAX_REASON_CHARS = 1000
MAX_BODY_BYTES = 16_384


def complete(judgment: dict, retrieval: bool) -> bool:
    """A judgment is finished when every field the rubric asks for is recorded."""
    return (judgment.get('correctness') in (0, 1, 2)
            and isinstance(judgment.get('abstention'), bool)
            and bool(str(judgment.get('reason') or '').strip())
            # Citation support is N/A (null) only for an abstention.
            and (not retrieval or judgment['abstention'] or judgment.get('citation_support') in (0, 1)))


class Store:
    """The frozen outputs plus the judgments file being filled in."""

    def __init__(self, raw: Path, judgments: Path, references: Path = REFERENCES):
        self.raw, self.path = raw, judgments
        self.lock = threading.Lock()
        self.rows = [json.loads(line) for line in raw.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.refs = {r['id']: r for r in json.loads(references.read_text(encoding='utf-8'))}
        if not judgments.exists():
            raise RuntimeError(f'{judgments} does not exist. Create it with: '
                               'uv run python -m bls_rag.evaluation.finetune_scoring template')
        self.judgments = json.loads(judgments.read_text(encoding='utf-8'))
        if self.judgments.get('raw_sha256') != hashlib.sha256(raw.read_bytes()).hexdigest():
            raise RuntimeError(f'{judgments} is bound to different outputs than {raw}.')
        self.arms = {name: {'model': arm['model'], 'retrieval': arm['retrieval']}
                     for name, arm in self.rows[0]['arms'].items()}

    def progress(self) -> dict:
        gradable = [(row['id'], name) for row in self.rows for name, out in row['arms'].items() if not out['error']]
        done = sum(complete(self.judgments['cases'][i][name], self.arms[name]['retrieval']) for i, name in gradable)
        return {'graded': done, 'total': len(gradable)}

    def data(self) -> dict:
        cases = []
        for row in self.rows:
            ref = self.refs[row['id']]
            gold = {(e['filename'], e['pdf_page']) for e in ref['evidence']}
            cases.append({
                'id': row['id'], 'question': row['question'], 'answerable': ref['answerability'] == 'answerable',
                'reference_answer': ref['reference_answer'], 'required_criteria': ref['required_criteria'],
                'evidence': ref['evidence'],
                'passages': [{'rank': c['rank'], 'source': c['source'], 'page': c['page'], 'content': c['content'],
                              'reference': (c['source'], c['page']) in gold} for c in row['retrieved_chunks']],
                'answers': {name: {'answer': out['answer'], 'error': out['error'],
                                   'exact_abstention': bool(out['answer']) and ABSTENTION in out['answer']}
                            for name, out in row['arms'].items()}})
        with self.lock:
            return {'arms': self.arms, 'cases': cases, 'judgments': self.judgments['cases'],
                    'progress': self.progress(), 'file': str(self.path), 'abstention_sentence': ABSTENTION}

    def save(self, payload: dict) -> dict:
        """Validate one judgment, write the file atomically and return the new progress."""
        case, arm = payload.get('id'), payload.get('arm')
        if case not in self.judgments['cases'] or arm not in self.arms:
            raise webui.RequestError(400, 'Unknown question or arm.')
        entry = {'correctness': payload.get('correctness'), 'reason': payload.get('reason') or '',
                 'abstention': payload.get('abstention')}
        if entry['correctness'] not in (None, 0, 1, 2) or isinstance(entry['correctness'], bool):
            raise webui.RequestError(400, 'Correctness must be 0, 1 or 2.')
        if entry['abstention'] not in (None, True, False):
            raise webui.RequestError(400, 'Abstention must be true or false.')
        if not isinstance(entry['reason'], str) or len(entry['reason']) > MAX_REASON_CHARS:
            raise webui.RequestError(400, f'Reasons are limited to {MAX_REASON_CHARS} characters.')
        entry['reason'] = entry['reason'].strip()
        if self.arms[arm]['retrieval']:
            entry['citation_support'] = payload.get('citation_support')
            if entry['citation_support'] not in (None, 0, 1) or isinstance(entry['citation_support'], bool):
                raise webui.RequestError(400, 'Citation support must be 0, 1 or empty.')
        with self.lock:
            self.judgments['cases'][case][arm] = entry
            temporary = self.path.with_name(self.path.name + '.tmp')
            temporary.write_text(json.dumps(self.judgments, indent=2) + '\n', encoding='utf-8')
            os.replace(temporary, self.path)
            return {'judgment': entry, 'progress': self.progress()}

    def summary(self) -> dict:
        """Run the project's own summary once everything is graded."""
        if self.path.resolve() != scoring.JUDGMENTS.resolve():
            raise webui.RequestError(409, f'The summary reads {scoring.JUDGMENTS}. Copy this file there first.')
        with self.lock:
            progress = self.progress()
            if progress['graded'] < progress['total']:
                raise webui.RequestError(409, f'{progress["total"] - progress["graded"]} answers still need grading.')
            try:
                result = scoring.summary()
            except SystemExit as exc:
                raise webui.RequestError(409, str(exc)) from None
        return {'arms': result['arms'], 'files': [str(scoring.OUT / 'summary.json'), str(scoring.OUT / 'comparison.md')]}


class Handler(webui.Handler):
    """Reuses the localhost check, JSON helpers and corpus-PDF serving of the question UI."""

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path.startswith('/pdf/'):
            super().do_GET()
        elif not self._local_request():
            return
        elif path == '/':
            self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
        elif path == '/api/data':
            self._json(200, self.server.store.data())
        else:
            self._json(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self._local_request():
            return
        try:
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise webui.RequestError(415, 'Send JSON.')
            length = int(self.headers.get('Content-Length') or 0)
            if not 0 < length <= MAX_BODY_BYTES:
                raise webui.RequestError(413, 'The request is empty or too large.')
            try:
                payload = json.loads(self.rfile.read(length))
            except ValueError:
                raise webui.RequestError(400, 'The request was not valid JSON.') from None
            if not isinstance(payload, dict):
                raise webui.RequestError(400, 'The request was not valid JSON.')
            if self.path == '/api/judgment':
                self._json(200, self.server.store.save(payload))
            elif self.path == '/api/summary':
                self._json(200, self.server.store.summary())
            else:
                self._json(404, {'error': 'Not found.'})
        except webui.RequestError as exc:
            self._json(exc.status, {'error': str(exc)})
        except OSError as exc:
            self._json(500, {'error': f'Could not save: {exc}'})


def make_server(store: Store, port: int = 8010) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.store = store
    return server


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--no-browser', action='store_true', help='Do not open the browser automatically')
    parser.add_argument('--judgments', type=Path, default=scoring.JUDGMENTS,
                        help='Judgments file to fill in (default: the experiment file; use a copy for a second grader)')
    args = parser.parse_args(argv)
    try:
        if args.judgments == scoring.JUDGMENTS and not scoring.JUDGMENTS.exists():
            scoring.template()
        server = make_server(Store(scoring.RAW, args.judgments), args.port)
    except (RuntimeError, OSError) as exc:
        raise SystemExit(f'ERROR: {exc}') from exc
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'Grading {args.judgments}\nOpen {url}  (Ctrl+C to stop; every change is saved immediately)')
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
