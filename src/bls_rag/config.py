"""Runtime settings, read from the environment (and an optional local .env)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from bls_rag.paths import ROOT

load_dotenv(ROOT / '.env')

COLLECTION = 'wa_business_economic_documents'
BASE_MODEL = 'llama3.1:8b'


def config(**overrides: Any) -> dict[str, Any]:
    """Return the current settings. Generation is always local Ollama."""
    settings = {
        'provider': 'ollama',
        'chat_model': os.getenv('OLLAMA_MODEL', BASE_MODEL).strip(),
        'ollama_base_url': os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/'),
        'embedding_model': os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
        'chunk_size': int(os.getenv('CHUNK_SIZE', '1000')),
        'chunk_overlap': int(os.getenv('CHUNK_OVERLAP', '180')),
        'top_k': int(os.getenv('TOP_K', '4')),
        'candidate_k': int(os.getenv('CANDIDATE_K', '16')),
        'retrieval_mode': os.getenv('RETRIEVAL_MODE', 'hybrid').lower(),
        'request_timeout_seconds': float(os.getenv('OLLAMA_REQUEST_TIMEOUT_SECONDS', '180')),
        'generation_deadline_seconds': float(os.getenv('OLLAMA_DEADLINE_SECONDS', '240')),
        'max_output_tokens': int(os.getenv('OLLAMA_NUM_PREDICT', '1024')),
        'num_ctx': int(os.getenv('OLLAMA_NUM_CTX', '8192')),
        'temperature': float(os.getenv('OLLAMA_TEMPERATURE', '0')),
        'seed': int(os.getenv('OLLAMA_SEED', '42')),
        'keep_alive': os.getenv('OLLAMA_KEEP_ALIVE', '10m'),
        'request_attempts': 1,
        'context_unit': 'pdf_page',
        'max_page_chars': 5000,
    }
    unknown = set(overrides) - set(settings)
    if unknown:
        raise KeyError(f'Unknown settings: {sorted(unknown)}')
    settings.update(overrides)
    return settings


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
