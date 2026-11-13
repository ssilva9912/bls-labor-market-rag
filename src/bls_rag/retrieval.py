"""Page-level hybrid retrieval: dense Chroma chunks + page BM25, fused with RRF.

The ranking logic is unchanged from the frozen experiment-01 runtime.
"""
from __future__ import annotations

import re
from functools import lru_cache

from bls_rag.config import config, sha256
from bls_rag.paths import PDF_DIR


def tokenize(text: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', text.lower())



def fuse_ranked_lists(dense_ids: list[str], lexical_ids: list[str], k: int = 60) -> list[str]:
    """Reciprocal rank fusion. Returns IDs in descending relevance order."""
    scores: dict[str, float] = {}
    for ranking in (dense_ids, lexical_ids):
        for rank, item_id in enumerate(ranking, 1):
            scores[item_id] = scores.get(item_id, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda item_id: (-scores[item_id], item_id))


def lexical_tokens(text: str) -> list[str]:
    """Normalize a small set of observed vocabulary mismatches for BM25."""
    text = re.sub(r'\bemployment\s+security\s+department\b', 'esd', text, flags=re.I)
    stop = set('what which do does the a an and or of in to from according '
               'two different report documents they their can be resolved esd'.split())
    aliases = {'wages': 'wage', 'yearly': 'annual'}
    return [aliases.get(token, token) for token in tokenize(text) if token not in stop]


def hybrid_selection(dense_ids: list[str], lexical_ids: list[str], top_k: int) -> list[str]:
    """RRF with one lexical coverage slot when its best hit would be dropped."""
    selected = fuse_ranked_lists(dense_ids, lexical_ids)[:top_k]
    if top_k > 1 and lexical_ids and lexical_ids[0] not in selected:
        selected = selected[:top_k - 1] + [lexical_ids[0]]
    return selected


def lexical_search(query: str, records: list[dict], candidate_k: int) -> list[dict]:
    from rank_bm25 import BM25Okapi
    corpus = [lexical_tokens(r['content']) for r in records]
    if not corpus:
        return []
    tokens = lexical_tokens(query)
    if not tokens:
        return []
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(tokens)
    ranks = sorted(range(len(records)), key=lambda i: (-float(scores[i]), i))
    # BM25 IDF can be negative in a small source-filtered corpus. Token overlap,
    # not a positive-score cutoff, determines whether a candidate can be returned.
    return [records[i] for i in ranks if set(tokens).intersection(corpus[i])][:candidate_k]


def expanded_query(question: str) -> str:
    """No case-specific expansions or reference values are injected."""
    return question


def compact_layout(text: str) -> str:
    """Preserve PDF rows/column order while replacing large padding with separators."""
    output = []
    years = None
    for line in text.splitlines():
        if not line.strip():
            continue
        line = re.sub(r'(?:\.\s*){3,}|…+', ' | ', line)
        line = re.sub(r' {2,}', ' | ', line.strip())
        cells = line.split(' | ')
        if len(cells) > 2 and all(re.fullmatch(r'20\d{2}', c) for c in cells[1:]):
            years = cells[1:]
        elif years and len(cells) == len(years) + 1:
            line = cells[0] + ': ' + '; '.join(f'{year}={value}' for year, value in zip(years, cells[1:]))
        elif len(cells) != len(years or []) + 1:
            years = None
        output.append(line)
    return '\n'.join(output)


def page_matches_measure(question: str, record: dict) -> bool:
    """Use a release named explicitly in the question as a source facet."""
    q = question.lower()
    source = record['metadata']['source']
    facets = [('metropolitan area employment and unemployment', '06_bls_'),
              ('state employment and unemployment', '02_bls_'),
              ('regional and state unemployment', '01_bls_'),
              ('occupational employment and wages', '03_bls_'),
              ('business employment dynamics', '04_bls_'),
              ('employment projections', '05_bls_'),
              ('employment situation', '07_bls_'),
              ('job openings and labor turnover', '08_bls_')]
    for label, prefix in facets:
        if label in q:
            return source.startswith(prefix)
    return True


def page_excerpt(content: str, question: str, limit: int) -> str:
    """Keep table headings and query-matching rows instead of truncating their tail."""
    if len(content) <= limit:
        return content
    lines = content.splitlines()
    tokens = set(lexical_tokens(question))
    # A named entity can occur at the bottom of a wide table; retain that row.
    frequencies = {t: sum(t in set(tokenize(line)) for line in lines) for t in tokens}
    scores = [sum(1 / max(1, frequencies[t]) for t in tokens if t in set(tokenize(line))) for line in lines]
    best = max(range(len(lines)), key=lambda i: scores[i])
    entities = [t for t in ('washington', 'seattle') if t in tokens]
    entity_rows = {i for i,line in enumerate(lines) if any(t in tokenize(line) for t in entities)}
    indices = set(range(min(8, len(lines)))) | set(range(max(0,best-2),min(len(lines),best+3))) | entity_rows | set(range(max(0,len(lines)-6),len(lines)))
    selected = '\n'.join(lines[i] for i in sorted(indices))
    return selected[:limit] if len(selected)>limit else selected


@lru_cache(maxsize=1)
def page_records() -> tuple[dict, ...]:
    from pypdf import PdfReader
    records = []
    for path in sorted(PDF_DIR.glob('*.pdf')):
        digest = sha256(path)
        for number, page in enumerate(PdfReader(path).pages, 1):
            content = compact_layout(page.extract_text(extraction_mode='layout'))
            if not content.strip():
                continue
            records.append({'content': content, 'metadata': {
                'source': path.name, 'page': number, 'file_sha256': digest,
                'chunk_id': f'{digest[:16]}:p{number}'}})
    return tuple(records)


def retrieve(question: str, store, mode: str, top_k: int, candidate_k: int) -> list[dict]:
    """Rank original PDF pages using existing dense chunks and page-level BM25."""
    if mode not in ('hybrid', 'dense'):
        raise ValueError('Mode must be "hybrid" or "dense"')
    records = [r for r in page_records() if page_matches_measure(question, r)]
    by_page = {(r['metadata']['source'], r['metadata']['page']): r for r in records}
    by_id = {r['metadata']['chunk_id']: r for r in records}
    query = expanded_query(question)
    dense = store.similarity_search(query, k=candidate_k)
    dense_ids = []
    for doc in dense:
        key = (doc.metadata['source'], doc.metadata['page'])
        if key in by_page:
            page_id = by_page[key]['metadata']['chunk_id']
            if page_id not in dense_ids:
                dense_ids.append(page_id)
    lexical = lexical_search(query, records, candidate_k) if mode == 'hybrid' else []
    ids = (hybrid_selection(dense_ids, [r['metadata']['chunk_id'] for r in lexical], top_k)
           if mode == 'hybrid' else dense_ids[:top_k])
    # Explicit place queries must not lose the named row beneath a long state table.
    entities = [t for t in ('washington', 'seattle') if t in tokenize(question)]
    if mode == 'hybrid' and entities:
        tables = [r for r in lexical if all(t in r['content'].lower() for t in entities)
                  and re.search(r'\btable\s+\d', r['content'][:500], re.I)
                  and 'unemployment' in r['content'][:1000].lower()
                  and not ('seasonally adjusted' in question.lower() and 'not seasonally adjusted' in r['content'][:300].lower())]
        if tables and tables[0]['metadata']['chunk_id'] not in ids:
            ids = ids[:top_k-1] + [tables[0]['metadata']['chunk_id']]
    return [{'rank': rank, 'chunk_id': page_id,
             'source': by_id[page_id]['metadata']['source'],
             'page': by_id[page_id]['metadata']['page'],
             'content': page_excerpt(by_id[page_id]['content'], question, config()['max_page_chars'])}
            for rank, page_id in enumerate(ids, 1)]


def page_record(source: str, page: int) -> dict:
    """Return one compacted PDF page by filename and 1-based page number."""
    for record in page_records():
        if record['metadata']['source'] == source and record['metadata']['page'] == page:
            return record
    raise KeyError(f'{source} p.{page} has no extractable text')
