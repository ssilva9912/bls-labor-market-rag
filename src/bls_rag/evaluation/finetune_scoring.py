"""Experiment 02: manual-judgment template, automatic format checks and the arm comparison.

    uv run python -m bls_rag.evaluation.finetune_scoring template   # after `bls-rag experiment run`
    # fill in artifacts/judgments.json against the PDFs (experiment-01 rubric)
    uv run python -m bls_rag.evaluation.finetune_scoring summary

Correctness (0/1/2) and citation support (0/1) are manual, using the frozen
experiment-01 rubric and reference answers; judgments are bound to the raw
outputs by SHA-256 so changed outputs cannot inherit scores. Format compliance
is computed automatically and needs no judgment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from statistics import mean

from bls_rag.generation import ABSTENTION
from bls_rag.paths import FINETUNE_DIR, RAG_EVAL_DIR

OUT = FINETUNE_DIR / 'artifacts'
RAW = OUT / 'outputs.jsonl'
JUDGMENTS = OUT / 'judgments.json'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows():
    return [json.loads(line) for line in RAW.read_text(encoding='utf-8').splitlines() if line.strip()]


def format_checks(answer: str | None, passages: int, retrieval: bool) -> dict:
    """Objective answer-format properties the fine-tune targets."""
    if not answer:
        return {'completed': False}
    cites = [int(n) for n in re.findall(r'\[S(\d+)\]', answer)]
    abstained = ABSTENTION in answer
    result = {'completed': True, 'exact_abstention': abstained, 'words': len(answer.split())}
    if retrieval:
        result.update({
            'has_citation': bool(cites),
            'citations_in_range': all(1 <= n <= passages for n in cites),
            'has_sources_line': bool(re.search(r'(?im)^\s*\**sources?\**\s*:', answer)),
        })
    return result


def template() -> None:
    if JUDGMENTS.exists():
        raise SystemExit(f'{JUDGMENTS} exists; refusing to overwrite manual judgments.')
    rows = _rows()
    cases = {}
    for row in rows:
        cases[row['id']] = {name: {'correctness': None, 'reason': '', 'abstention': None,
                                   **({'citation_support': None} if arm['retrieval'] else {})}
                            for name, arm in row['arms'].items()}
    JUDGMENTS.write_text(json.dumps({
        'method': 'Manual judgments against the saved PDFs using experiment-01 scoring_rubric.md and references.json. '
                  'correctness 0/1/2; citation_support 0/1 for factual RAG answers, null for pure abstentions; '
                  'abstention true/false. Grade blind to arm where possible.',
        'raw_sha256': _sha(RAW), 'cases': cases}, indent=2) + '\n', encoding='utf-8')
    print('Wrote', JUDGMENTS)


def summary() -> dict:
    rows = _rows()
    judgments = json.loads(JUDGMENTS.read_text(encoding='utf-8'))
    if judgments['raw_sha256'] != _sha(RAW):
        raise SystemExit('Judgments are bound to different outputs; re-judge the current outputs.')
    refs = {r['id']: r for r in json.loads((RAG_EVAL_DIR / 'references.json').read_text(encoding='utf-8'))}
    arms = list(rows[0]['arms'])
    result = {'questions': len(rows), 'answerable': sum(refs[r['id']]['answerability'] == 'answerable' for r in rows),
              'arms': {}}
    for arm in arms:
        graded, formats, cites, secs, tokens = [], [], [], [], []
        for row in rows:
            out, j = row['arms'][arm], judgments['cases'][row['id']][arm]
            if out['error']:
                continue
            if j['correctness'] not in (0, 1, 2):
                raise SystemExit(f'Missing correctness for {row["id"]}/{arm}')
            graded.append((row['id'], j))
            formats.append(format_checks(out['answer'], len(row['retrieved_chunks']), out['retrieval']))
            if out['retrieval'] and j.get('citation_support') is not None:
                cites.append(j['citation_support'])
            secs.append(out['call']['elapsed_seconds'])
            tokens.append((out['call'].get('ollama_metrics') or {}).get('eval_count'))
        answerable = [(i, j) for i, j in graded if refs[i]['answerability'] == 'answerable']
        fmt = {k: sum(bool(f.get(k)) for f in formats) for k in
               ('has_citation', 'citations_in_range', 'has_sources_line', 'exact_abstention') if any(k in f for f in formats)}
        result['arms'][arm] = {
            'model': rows[0]['arms'][arm]['model'], 'retrieval': rows[0]['arms'][arm]['retrieval'],
            'completed': len(graded), 'errors': [r['id'] for r in rows if r['arms'][arm]['error']],
            'points': sum(j['correctness'] for _, j in graded), 'possible_points': 2 * len(graded),
            'fully_correct': sum(j['correctness'] == 2 for _, j in graded),
            'answerable_points': sum(j['correctness'] for _, j in answerable),
            'answerable_possible_points': 2 * len(answerable),
            'abstentions': [i for i, j in graded if j['abstention']],
            'citation_supported': sum(cites) if cites else None, 'citation_eligible': len(cites) or None,
            'format': fmt, 'mean_words': round(mean(f['words'] for f in formats), 1) if formats else None,
            'mean_generation_seconds': round(mean(secs), 3) if secs else None,
            'mean_output_tokens': round(mean(t for t in tokens if t), 1) if any(tokens) else None,
        }
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    head = '|Arm|Model|Passages|Points|Fully correct|Answerable pts|Citations supported|Has [S#]|Sources line|Mean s|'
    lines = ['# Experiment 02: base vs fine-tuned', '', head, '|' + '---|' * 10]
    for arm, s in result['arms'].items():
        c = f'{s["citation_supported"]}/{s["citation_eligible"]}' if s['citation_eligible'] else 'n/a'
        n = s['completed']
        lines.append(f'|{arm}|{s["model"]}|{"yes" if s["retrieval"] else "no"}|{s["points"]}/{s["possible_points"]}'
                     f'|{s["fully_correct"]}/{n}|{s["answerable_points"]}/{s["answerable_possible_points"]}|{c}'
                     f'|{s["format"].get("has_citation", "n/a")}/{n}|{s["format"].get("has_sources_line", "n/a")}/{n}'
                     f'|{s["mean_generation_seconds"]}|')
    (OUT / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return result


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('command', choices=['template', 'summary'])
    {'template': template, 'summary': summary}[parser.parse_args(argv).command]()


if __name__ == '__main__':
    main()
