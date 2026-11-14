"""Freeze, validate and run a paired experiment exactly once.

An experiment directory holds an ``experiment.json`` such as::

    {"questions": "questions.json",
     "arms": [{"name": "base_rag", "model": "llama3.1:8b", "retrieval": true},
              {"name": "ft_rag",   "model": "llama3.1-bls-ft", "retrieval": true}]}

``freeze`` records settings, installed model digests and the hashes of every
input (corpus, questions, index, package source). ``run`` refuses to start if
any of them changed and refuses to overwrite earlier outputs, so scored
results can always be traced back to exactly what produced them.

Experiment 01 predates this generalisation; its frozen manifest is verified
offline by :mod:`bls_rag.evaluation.verify`.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from bls_rag import generation, index, retrieval
from bls_rag.config import config, sha256
from bls_rag.paths import INDEX_DIR, PDF_DIR, ROOT, SOURCE_INVENTORY

PACKAGES = ['langchain-chroma', 'langchain-ollama', 'langchain-huggingface', 'langchain-community',
            'langchain-text-splitters', 'langchain-core', 'chromadb', 'sentence-transformers',
            'transformers', 'torch', 'numpy', 'pypdf', 'rank-bm25', 'python-dotenv', 'ollama', 'httpx']


def _spec(directory: Path) -> dict:
    spec = json.loads((directory / 'experiment.json').read_text(encoding='utf-8'))
    names = [a['name'] for a in spec['arms']]
    if len(set(names)) != len(names):
        raise ValueError('Arm names must be unique')
    return spec


def _inputs(directory: Path, spec: dict) -> list[Path]:
    source = sorted((ROOT / 'src' / 'bls_rag').rglob('*.py'))
    return [directory / 'experiment.json', directory / spec['questions'], SOURCE_INVENTORY,
            *sorted(PDF_DIR.glob('*.pdf')), INDEX_DIR / 'manifest.json', INDEX_DIR / 'chunks.jsonl',
            *(p for p in source if '__pycache__' not in p.parts)]


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def freeze(directory: Path) -> None:
    manifest = directory / 'freeze_manifest.json'
    if manifest.exists():
        raise SystemExit(f'{manifest} already exists; refusing to replace it.')
    spec = _spec(directory)
    settings = config()
    identities = {a['model']: generation.model_identity(config(chat_model=a['model'])) for a in spec['arms']}
    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    data = {'frozen_utc': datetime.now(timezone.utc).isoformat(), 'experiment': directory.name,
            'arms': spec['arms'], 'settings': settings, 'model_identities': identities,
            'ollama_version': generation.ollama_json('/api/version'),
            'python': platform.python_version(), 'platform': platform.platform(),
            'package_versions': versions,
            'hashes': {_rel(p): sha256(p) for p in _inputs(directory, spec)}}
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Frozen:', manifest)


def validate(directory: Path) -> dict:
    data = json.loads((directory / 'freeze_manifest.json').read_text(encoding='utf-8'))
    for name, expected in data['hashes'].items():
        if sha256(ROOT / name) != expected:
            raise RuntimeError(f'Frozen input changed: {name}')
    for model, identity in data['model_identities'].items():
        if generation.model_identity(config(chat_model=model))['digest'] != identity['digest']:
            raise RuntimeError(f'Installed model digest differs from freeze: {model}')
    print('Validated', len(data['hashes']), 'frozen inputs and', len(data['model_identities']), 'models')
    return data


def run(directory: Path) -> Path:
    manifest = validate(directory)
    spec = _spec(directory)
    out = directory / 'artifacts' / 'outputs.jsonl'
    if out.exists():
        raise SystemExit(f'{out} exists. No rerun or overwrite is permitted.')
    out.parent.mkdir(parents=True, exist_ok=True)
    base = manifest['settings']
    store = index.load_chroma() if any(a['retrieval'] for a in spec['arms']) else None
    questions = json.loads((directory / spec['questions']).read_text(encoding='utf-8'))
    freeze_hash = sha256(directory / 'freeze_manifest.json')
    with out.open('x', encoding='utf-8') as output:
        for case in questions:
            row = {'id': case['id'], 'question': case['question'], 'freeze_sha256': freeze_hash,
                   'retrieved_chunks': [], 'retrieval_seconds': None, 'retrieval_error': None, 'arms': {}}
            started = time.monotonic()
            try:
                row['retrieved_chunks'] = retrieval.retrieve(case['question'], store, base['retrieval_mode'],
                                                             base['top_k'], base['candidate_k'])
                row['retrieval_seconds'] = round(time.monotonic() - started, 3)
            except Exception as exc:
                row['retrieval_error'] = {'category': 'retrieval_failure', 'type': type(exc).__name__}
            for arm in spec['arms']:
                result = {'model': arm['model'], 'retrieval': arm['retrieval'], 'answer': None,
                          'error': None, 'call': None}
                llm = generation.get_llm({**base, 'chat_model': arm['model']})
                try:
                    if arm['retrieval'] and row['retrieval_error']:
                        raise RuntimeError('retrieval failed')
                    result['answer'] = (generation.answer_rag(llm, case['question'], row['retrieved_chunks'])
                                        if arm['retrieval'] else generation.answer_baseline(llm, case['question']))
                except Exception as exc:
                    result['error'] = {'category': getattr(exc, 'category', 'runtime_failure'),
                                       'type': type(exc).__name__}
                result['call'] = llm.last_call
                row['arms'][arm['name']] = result
                print(case['id'], arm['name'], result['error'] or result['answer'][:120].replace('\n', ' '), flush=True)
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
            output.flush()
    validate(directory)
    print('Outputs preserved:', out)
    return out


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('command', choices=['freeze', 'validate', 'run'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    {'freeze': freeze, 'validate': validate, 'run': run}[args.command](args.directory.resolve())


if __name__ == '__main__':
    main()
