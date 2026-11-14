"""Repository layout in one place.

The first experiment was frozen under an older, flat layout (``docs/``,
``artifacts/``, ``questions.json`` at the root). Its manifest still records
those historical paths, so :func:`legacy_path` translates them to where the
same, byte-identical files now live.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get('BLS_RAG_ROOT', Path(__file__).resolve().parents[2]))

CORPUS_DIR = ROOT / 'corpus'
PDF_DIR = CORPUS_DIR / 'pdfs'
SOURCE_INVENTORY = CORPUS_DIR / 'source_inventory.json'
PROVENANCE_DIR = CORPUS_DIR / 'provenance'

INDEX_DIR = ROOT / 'index'
RESULTS_DIR = ROOT / 'results'

EXPERIMENTS_DIR = ROOT / 'experiments'
RAG_EVAL_DIR = EXPERIMENTS_DIR / '01_rag_eval'
FINETUNE_DIR = EXPERIMENTS_DIR / '02_finetune'

# Runtime code whose exact bytes were frozen for experiment 01. It was later
# refactored into this package; the frozen bytes remain verifiable at the
# ``submission-v1`` Git tag and in the release ZIP.
FROZEN_AT_TAG = 'submission-v1'
LEGACY_RUNTIME_FILES = {'rag_eval.py', 'model_worker.py', 'final_evaluation.py', 'sources.py'}

_LEGACY_EXPERIMENT_FILES = {'questions.json', 'references.json', 'scoring_rubric.md',
                            'freeze_manifest.json', 'submission_checksums.json'}


def legacy_path(name: str, experiment_dir: Path = RAG_EVAL_DIR) -> Path | None:
    """Map a path recorded in the experiment-01 freeze to its current location.

    Returns ``None`` for runtime code that now only exists at the frozen tag.
    """
    if name in LEGACY_RUNTIME_FILES:
        return None
    if name == 'docs/source_inventory.json':
        return SOURCE_INVENTORY
    if name.startswith('docs/'):
        return PDF_DIR / name.removeprefix('docs/')
    if name.startswith('provenance/'):
        return CORPUS_DIR / name
    if name.startswith('artifacts/') or name in _LEGACY_EXPERIMENT_FILES:
        return experiment_dir / name
    if name.startswith('index/'):
        return INDEX_DIR / name.removeprefix('index/')
    return ROOT / name
