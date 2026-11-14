"""Local embedding index: PDF parsing, chunking and the persisted Chroma store."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from bls_rag.config import COLLECTION, config, sha256
from bls_rag.paths import INDEX_DIR, PDF_DIR, ROOT


def get_embeddings():
    """Local CPU Sentence Transformers; never downloads at runtime."""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name=config()['embedding_model'],
        model_kwargs={'device': 'cpu', 'local_files_only': True},
        encode_kwargs={'normalize_embeddings': True},
    )


def load_chroma():
    from langchain_chroma import Chroma

    manifest_path = INDEX_DIR / 'manifest.json'
    if not manifest_path.exists():
        raise RuntimeError('No index exists. Run: uv run bls-rag ingest')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if config()['embedding_model'] != manifest['embedding_model']:
        raise RuntimeError(f'Index uses {manifest["embedding_model"]}; set EMBEDDING_MODEL to match or re-ingest.')
    return Chroma(collection_name=COLLECTION, persist_directory=str(INDEX_DIR / 'chroma'),
                  embedding_function=get_embeddings())


def ingest(docs_dir: Path = PDF_DIR) -> None:
    from langchain_chroma import Chroma
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from bls_rag.corpus import verify

    cfg = config()
    if cfg['chunk_overlap'] >= cfg['chunk_size']:
        raise ValueError('CHUNK_OVERLAP must be smaller than CHUNK_SIZE')
    verify()
    paths = sorted(docs_dir.glob('*.pdf'))
    if not paths:
        raise RuntimeError(f'No PDFs found in {docs_dir}.')
    print(f'Found {len(paths)} PDFs. Parsing and deduplicating by file hash...')

    pages, seen, skipped_empty = [], {}, []
    for pdf in paths:
        digest = sha256(pdf)
        if digest in seen:
            print(f'  Duplicate skipped: {pdf.name} (same bytes as {seen[digest]})')
            continue
        seen[digest] = pdf.name
        extracted = 0
        for page in PyPDFLoader(str(pdf)).load():
            if not page.page_content.strip():
                continue
            # Preserve provenance, with a 1-indexed page number for reports.
            page.metadata = {'source': pdf.name, 'page': int(page.metadata.get('page', 0)) + 1,
                             'file_sha256': digest}
            pages.append(page)
            extracted += 1
        if extracted == 0:
            skipped_empty.append(pdf.name)
            print(f'  WARNING: No extractable text in {pdf.name}; scanned PDFs may require OCR.')
    if not pages:
        raise RuntimeError('No extractable text in source documents.')

    splitter = RecursiveCharacterTextSplitter(chunk_size=cfg['chunk_size'], chunk_overlap=cfg['chunk_overlap'])
    chunks = splitter.split_documents(pages)
    for i, chunk in enumerate(chunks):
        identity = f'{chunk.metadata["file_sha256"]}:{chunk.metadata["page"]}:{i}:{chunk.page_content}'
        chunk.metadata['chunk_id'] = hashlib.sha256(identity.encode()).hexdigest()[:24]

    # Only replace the existing index after every PDF parsed successfully.
    if INDEX_DIR.exists():
        if INDEX_DIR.resolve() != (ROOT / 'index').resolve():
            raise RuntimeError('Refusing to replace an index outside this project')
        shutil.rmtree(INDEX_DIR)
    INDEX_DIR.mkdir(parents=True)
    store = Chroma(collection_name=COLLECTION, persist_directory=str(INDEX_DIR / 'chroma'),
                   embedding_function=get_embeddings())
    print(f'Embedding {len(chunks)} chunks on the local CPU...')
    for start in range(0, len(chunks), 100):
        batch = chunks[start:start + 100]
        store.add_documents(batch, ids=[d.metadata['chunk_id'] for d in batch])
    with (INDEX_DIR / 'chunks.jsonl').open('w', encoding='utf-8') as f:
        for doc in chunks:
            f.write(json.dumps({'content': doc.page_content, 'metadata': doc.metadata}, ensure_ascii=False) + '\n')
    manifest = {
        'embedding_model': cfg['embedding_model'],
        'chunk_size': cfg['chunk_size'], 'chunk_overlap': cfg['chunk_overlap'],
        'num_pdf_files': len(seen), 'num_source_files': len(seen),
        'num_pages_with_text': len(pages), 'num_chunks': len(chunks), 'empty_pdfs': skipped_empty,
        'created_utc': datetime.now(timezone.utc).isoformat(),
    }
    (INDEX_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Indexed {len(seen)} documents, {len(pages)} text pages, {len(chunks)} chunks -> {INDEX_DIR}')
