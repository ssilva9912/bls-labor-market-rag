"""Freeze the assignment inputs, then run exactly one paired local evaluation."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import rag_eval as rag

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts'
MANIFEST = ROOT / 'freeze_manifest.json'
RUNTIME_FILES = ['rag_eval.py', 'model_worker.py', 'final_evaluation.py',
                 'questions.json', 'references.json', 'scoring_rubric.md', 'sources.py',
                 'docs/source_inventory.json', 'provenance/reuse_terms.json',
                 'index/manifest.json', 'index/chunks.jsonl']


def freeze():
    if MANIFEST.exists():
        raise SystemExit('Freeze already exists; refusing to replace it.')
    pdfs = sorted((ROOT / 'docs').glob('*.pdf'))
    questions = rag.read_questions(ROOT / 'questions.json')
    assert len(pdfs) == 8 and len(questions) == 9
    settings = rag.config()
    assert settings['chat_model'] == 'llama3.1:8b'
    identity = rag.model_identity()
    packages = ['langchain-chroma', 'langchain-ollama', 'langchain-huggingface',
                'langchain-community', 'langchain-text-splitters', 'langchain-core',
                'chromadb', 'sentence-transformers', 'transformers', 'torch', 'numpy',
                'pypdf', 'fonttools', 'rank-bm25', 'python-dotenv', 'ollama', 'httpx']
    data = {'frozen_utc': datetime.now(timezone.utc).isoformat(),
            'purpose': 'Final descriptive evaluation on tuned development questions; no held-out claim.',
            'documents': len(pdfs), 'questions': len(questions), 'settings': settings,
            'model_identity': identity, 'ollama_version': rag.ollama_json('/api/version'),
            'python': platform.python_version(), 'platform': platform.platform(),
            'package_versions': {p: importlib.metadata.version(p) for p in packages},
            'hashes': {str(p.relative_to(ROOT)).replace('\\', '/'): rag.sha256(p)
                       for p in [*(ROOT / p for p in RUNTIME_FILES), *pdfs]}}
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Frozen:', MANIFEST)


def validate():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for name, expected in data['hashes'].items():
        if rag.sha256(ROOT / name) != expected:
            raise RuntimeError(f'Frozen input changed: {name}')
    original_config = rag.config
    rag.config = lambda: dict(data['settings'])
    try:
        if rag.model_identity()['digest'] != data['model_identity']['digest']:
            raise RuntimeError('Installed model digest differs from freeze')
    except Exception:
        rag.config = original_config
        raise
    return data


def run():
    manifest = validate()
    OUT.mkdir(exist_ok=True)
    path = OUT / 'final_evaluation.jsonl'
    if path.exists():
        raise SystemExit('Final output exists. No rerun or overwrite is permitted.')
    store = rag.load_chroma()
    model = rag.get_llm()
    with path.open('x', encoding='utf-8') as output:
        for case in rag.read_questions(ROOT / 'questions.json'):
            print(case['id'], 'started', flush=True)
            row = {'id': case['id'], 'question': case['question'],
                   'original_question': case['original_question'], 'correction': case['correction'],
                   'freeze_sha256': rag.sha256(MANIFEST), 'provider': 'ollama',
                   'model_identity': manifest['model_identity'], 'settings': manifest['settings'],
                   'retrieved_chunks': [], 'rag_answer': None, 'baseline_answer': None,
                   'rag_error': None, 'baseline_error': None, 'rag_call': None, 'baseline_call': None}
            started = time.monotonic()
            try:
                row['retrieved_chunks'] = rag.retrieve(case['question'], store, 'hybrid',
                    manifest['settings']['top_k'], manifest['settings']['candidate_k'])
                row['retrieval_seconds'] = round(time.monotonic() - started, 3)
            except Exception as exc:
                row['rag_error'] = {'category': 'retrieval_failure', 'type': type(exc).__name__}
            for arm in ('rag', 'baseline'):
                if arm == 'rag' and row['rag_error']:
                    continue
                model.last_call = None
                try:
                    row[arm + '_answer'] = (rag.answer_rag(model, case['question'], row['retrieved_chunks'])
                        if arm == 'rag' else rag.answer_baseline(model, case['question']))
                except Exception as exc:
                    row[arm + '_error'] = {'category': getattr(exc, 'category', 'runtime_failure'),
                                           'type': type(exc).__name__}
                row[arm + '_call'] = model.last_call
                print(case['id'], arm, row[arm + '_error'] or row[arm + '_answer'], flush=True)
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
            output.flush()
    validate()
    print('Final paired outputs preserved:', path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('command', choices=['freeze', 'validate', 'run'])
    args = parser.parse_args()
    {'freeze': freeze, 'validate': validate, 'run': run}[args.command]()
