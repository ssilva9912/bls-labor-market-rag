# Experiment 01: RAG vs closed book (frozen)

Nine development questions (eight answerable, one intentional abstention, B9)
over the eight BLS PDFs; `llama3.1:8b` run once per question with and without
retrieval. Page-level hybrid retrieval (dense MiniLM chunks mapped to pages +
page BM25, reciprocal rank fusion), K=4.

| Measure | Result |
|---|---|
| RAG correctness | 12/18 points; 6/9 fully correct |
| No-retrieval correctness | 2/18 points; 1/9 fully correct |
| Macro Precision@4 (answerable) | 40.625% |
| Reference-evidence Recall@4 | 100% (8/8 canonical pages) |
| RAG citation support | 4/7 factual responses |

Read: [reflection (PDF)](artifacts/reflection.pdf) · [per-question comparison](artifacts/comparison.md) ·
[raw outputs](artifacts/final_evaluation.jsonl) · [manual judgments](artifacts/scoring_judgments.json) ·
[reference table](artifacts/source_reference_table.md) · [rubric](scoring_rubric.md)

## Files

- `questions.json`, `references.json`, `scoring_rubric.md`, `freeze_manifest.json`: frozen inputs.
- `artifacts/`: raw outputs, hash-bound manual judgments, metrics and the reflection.
- `runtime_versions.lock.txt`: the frozen run's direct package versions (evidence, not an install file).
- `PUBLICATION_REVIEW.md`, `publication_files.json`: the original publication record.

The manifest records paths from the original flat layout (`docs/`, `artifacts/`, ...);
`bls_rag.paths.legacy_path` maps them to their current locations. Regenerate
metrics and tables (no model calls) with:

```powershell
uv run python -m bls_rag.evaluation.scoring
uv run python -m bls_rag.evaluation.references
uv run --group docs python -m bls_rag.evaluation.report
```

These questions are reused unchanged as the **held-out test set** for experiment 02.
