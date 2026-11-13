"""Build the supervised fine-tuning set for experiment 02.

Each hand-written example in ``train_questions.json`` names its evidence
page(s) and a reference answer with ``{S:n}`` placeholders (n = 1-based index
into ``evidence``). The builder recreates what the model sees at inference:

* the exact :data:`bls_rag.generation.RAG_SYSTEM` prompt,
* PDF-page passages compacted and excerpted exactly like retrieval does,
* the gold page(s) mixed with BM25 distractor pages at a seeded random rank,

then rewrites the placeholders to the gold page's actual ``[S#]`` label and
appends a ``Sources:`` line. Unanswerable examples get distractors only and
the exact abstention sentence.

Contamination guard: no training context may contain a page that is a gold
reference page for the experiment-01 evaluation questions, and no training
question may reuse an evaluation question.

Every ``check`` string must appear in the gold excerpt (ignoring spaces and
the ``|`` column separators), so a number in an answer can never come from a
row the excerpt dropped.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from bls_rag.generation import ABSTENTION, rag_messages
from bls_rag.paths import FINETUNE_DIR, RAG_EVAL_DIR
from bls_rag.retrieval import lexical_search, page_excerpt, page_matches_measure, page_records

CHARS_PER_TOKEN = 3.6  # rough Llama 3 estimate for this corpus; the trainer reports exact counts


def _norm(text: str) -> str:
    return re.sub(r'[\s|]+', '', text).lower()


def eval_gold_pages() -> set[tuple[str, int]]:
    refs = json.loads((RAG_EVAL_DIR / 'references.json').read_text(encoding='utf-8'))
    return {(e['filename'], e['pdf_page']) for r in refs for e in r['evidence']}


def build_example(item: dict, records: list[dict], excluded: set, pages: int, max_chars: int) -> dict:
    by_key = {(r['metadata']['source'], r['metadata']['page']): r for r in records}
    gold_keys = [(e['filename'], e['pdf_page']) for e in item['evidence']]
    for key in gold_keys:
        if key in excluded:
            raise ValueError(f'{item["id"]}: evidence {key} is an evaluation gold page')
        if key not in by_key:
            raise ValueError(f'{item["id"]}: evidence {key} has no extractable text')

    pool = [r for r in records if page_matches_measure(item['question'], r)
            and (r['metadata']['source'], r['metadata']['page']) not in excluded
            and (r['metadata']['source'], r['metadata']['page']) not in gold_keys]
    distractors = lexical_search(item['question'], pool, pages)[:max(0, pages - len(gold_keys))]
    chosen = [by_key[k] for k in gold_keys] + distractors
    rng = random.Random(item['id'])
    rng.shuffle(chosen)

    chunks = [{'rank': rank, 'source': r['metadata']['source'], 'page': r['metadata']['page'],
               'content': page_excerpt(r['content'], item['question'], max_chars)}
              for rank, r in enumerate(chosen, 1)]
    rank_of = {(c['source'], c['page']): c['rank'] for c in chunks}

    gold_text = _norm(' '.join(c['content'] for c in chunks if (c['source'], c['page']) in gold_keys))
    for needle in item['check']:
        if _norm(needle) not in gold_text:
            raise ValueError(f'{item["id"]}: check {needle!r} not found in the gold excerpt')

    if item['answerability'] == 'unanswerable':
        answer = f'{ABSTENTION}\n\nSources: None'
    else:
        def label(match):
            return f'[S{rank_of[gold_keys[int(match.group(1)) - 1]]}]'
        body = re.sub(r'\{S:(\d+)\}', label, item['answer'])
        if '{S:' in body or not re.search(r'\[S\d\]', body):
            raise ValueError(f'{item["id"]}: answer must cite its evidence with {{S:n}}')
        cited = sorted({gold_keys[int(n) - 1] for n in re.findall(r'\{S:(\d+)\}', item['answer'])},
                       key=lambda k: rank_of[k])
        answer = body + '\n\nSources: ' + '; '.join(f'{f} (p. {p})' for f, p in cited)

    (system, prompt), (_, question) = rag_messages(item['question'], chunks)
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': question},
                {'role': 'assistant', 'content': answer}]
    return {'id': item['id'], 'answerability': item['answerability'], 'messages': messages,
            'context_pages': [f'{c["source"]} p.{c["page"]}' for c in chunks],
            'approx_tokens': round(sum(len(m['content']) for m in messages) / CHARS_PER_TOKEN)}


def build(source: Path, output: Path, pages: int, max_chars: int) -> list[dict]:
    items = json.loads(source.read_text(encoding='utf-8'))
    ids = [i['id'] for i in items]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate training IDs')
    eval_questions = {q['question'].strip().lower()
                      for q in json.loads((RAG_EVAL_DIR / 'questions.json').read_text(encoding='utf-8'))}
    if eval_questions & {i['question'].strip().lower() for i in items}:
        raise ValueError('A training question duplicates an evaluation question')
    records = list(page_records())
    excluded = eval_gold_pages()
    examples, errors = [], []
    for item in items:
        try:
            examples.append(build_example(item, records, excluded, pages, max_chars))
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError('Dataset checks failed:\n  ' + '\n  '.join(errors))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8', newline='\n') as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')
    return examples


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description='Build the experiment-02 SFT dataset (no model calls)')
    parser.add_argument('--source', type=Path, default=FINETUNE_DIR / 'train_questions.json')
    parser.add_argument('--output', type=Path, default=FINETUNE_DIR / 'data' / 'train.jsonl')
    parser.add_argument("--pages", type=int, default=3, help="Passages per example, gold included (inference uses 4; 3 fits 8 GB)")
    parser.add_argument('--max-page-chars', type=int, default=3500,
                        help='Per-page excerpt limit; inference uses 5000, lower keeps training within 8 GB VRAM')
    args = parser.parse_args(argv)
    examples = build(args.source, args.output, args.pages, args.max_page_chars)
    tokens = sorted(e['approx_tokens'] for e in examples)
    kinds = {k: sum(e['answerability'] == k for e in examples) for k in ('answerable', 'partial', 'unanswerable')}
    print(json.dumps({'examples': len(examples), **kinds, 'approx_tokens_median': tokens[len(tokens) // 2],
                      'approx_tokens_max': tokens[-1], 'output': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
