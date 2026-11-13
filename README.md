# bls-labor-market-rag

Local retrieval-augmented generation (RAG) and fine-tuning experiments over
**eight official BLS labor-market releases** (172 PDF pages). Everything runs on
one laptop: Ollama `llama3.1:8b` for generation, MiniLM embeddings and Chroma
for retrieval, and Unsloth QLoRA for fine-tuning. No hosted model APIs are used.

| Experiment | Question | Status |
|---|---|---|
| [01 – RAG vs closed book](experiments/01_rag_eval/) | Does page-level hybrid retrieval make an 8B model answer BLS questions correctly? | Done, frozen (`submission-v1`) |
| [02 – Fine-tuning](experiments/02_finetune/) | Does a small QLoRA fine-tune fix the *answer-format* failures RAG left behind, and is it worth it vs prompting/RAG? | Dataset built; training runs locally |

**Experiment 01 headline:** RAG scored 12/18 vs 2/18 without retrieval, and
reference-page recall@4 was 100%. The failures were in *generation*: a wrong
abstention on a table row (B1), a dropped "preliminary" footnote (B2), a
self-contradictory answer (B3), and 4 of 7 factual answers with fully supported
citations. Experiment 02 targets exactly that behaviour.

## Layout

```text
src/bls_rag/            The package: config, index, retrieval, generation, experiment runner, CLI
  evaluation/           Scoring, reports, offline verification and the experiment-02 grading page
  finetune_data.py      Builds the fine-tuning set from hand-written, PDF-checked examples
  webui.py, webui.html  Local browser UI (`bls-rag ui`)
corpus/                 The 8 BLS PDFs, source inventory and provenance (HTML cross-checks, reuse terms)
experiments/
  01_rag_eval/          Frozen questions, references, rubric, manifest and results of experiment 01
  02_finetune/          Training questions, generated dataset, held-out config and (later) results
finetune/               Separate uv project for GPU training (WSL2 + NVIDIA): train.py, export.py
scripts/                Ollama smoke test, frozen-tag check, publication/secret audit
tests/                  Offline tests; live Ollama/Chroma tests are opt-in
index/  results/        Local only, git-ignored
```

## Setup (uv)

Install [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com/download), then:

```powershell
uv sync                      # Python 3.12, locked dependencies, full local pipeline
uv run bls-rag corpus verify # PDF and provenance hashes, offline
uv run python -m unittest discover -s tests
```

`uv sync` installs the full pipeline (embeddings, Chroma, LangChain). CI and
quick checks can use the light core only: `uv sync --no-default-groups --group dev`.

### Run the RAG pipeline

```powershell
# One-time downloads (never done automatically): ~4.9 GB model + MiniLM embeddings
ollama pull llama3.1:8b
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

uv run bls-rag ingest
uv run bls-rag ask "What was Washington's annual average unemployment rate in 2024?"
uv run bls-rag ask "..." --model llama3.1-bls-ft     # after experiment 02
uv run bls-rag ask "..." --no-retrieval              # closed-book baseline
```

Settings come from environment variables or a local `.env` (see `.env.example`).

### Ask questions in the browser

```powershell
uv run bls-rag ui            # opens http://127.0.0.1:8000 (--port N, --no-browser)
```

A local page for the same pipeline as `bls-rag ask`: pick any installed Ollama
chat model (base or fine-tuned), answer from the documents or closed-book, and
see the pages the model was given, with a link that opens each PDF at that page.
It uses only the standard library, listens on localhost only, and answers each
question on its own (no chat memory).

### Experiments

```powershell
uv run bls-rag verify                             # re-verify experiment 01 evidence offline
uv run bls-rag experiment freeze experiments/02_finetune
uv run bls-rag experiment run    experiments/02_finetune
```

`freeze` records settings, model digests and the hash of every input;
`run` refuses to start if anything changed and never overwrites results.

## Reproducibility notes

- Experiment 01 was frozen under an earlier flat layout. Its data files were
  moved here byte-for-byte and are re-hashed by `bls-rag verify`. Its runtime
  code was later refactored into `src/bls_rag/`; the original frozen code is
  verified at the `submission-v1` tag with `uv run python -m scripts.verify_frozen_tag`.
  The graded submission is the [release ZIP](https://github.com/ssilva9912/bls-labor-market-rag/releases/tag/submission-v1).
- Retrieval logic is unchanged from experiment 01.
- `.gitattributes` disables line-ending conversion so hashed files keep their bytes on Windows.

## Sources and reuse

All eight PDFs are unmodified official BLS releases. BLS material is public
domain with attribution requested; see [third-party notices](THIRD_PARTY_NOTICES.md)
and `corpus/source_inventory.json` for URLs, dates and hashes.
