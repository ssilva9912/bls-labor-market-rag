# Experiment 02: Fine-tuning for grounded answer format

## Hypothesis

Experiment 01 showed retrieval already finds the right pages (reference recall@4
= 100%), but the 8B model mishandles them: it abstains when the row is present
(B1), drops a "preliminary" footnote (B2), contradicts itself (B3), and cites
the wrong page (B4). These are **behaviour and format** errors, which
fine-tuning is good at. Missing knowledge, which RAG supplies, is not what is
being trained. So the expectation is:

- **ft + RAG > base + RAG** on citation support and format, maybe on correctness.
- **ft closed-book ≈ base closed-book**: 44 examples should not teach BLS facts.
  If the closed-book score jumps, the fine-tune memorised data, which would be a warning sign.

## Design

| Choice | Value | Why |
|---|---|---|
| Base model | Llama 3.1 8B Instruct (Unsloth 4-bit for training, Ollama `llama3.1:8b` Q4_K_M for inference) | Same model as experiment 01 |
| Method | QLoRA, r=16, alpha=16, all attention + MLP projections, 3 epochs, lr 2e-4, effective batch 8 | Standard small-data settings; fits 8 GB |
| Training data | 44 hand-written examples: 34 answerable, 2 partial, 8 unanswerable | Assignment asks for 20–50 |
| Input | The exact inference prompt (`RAG_SYSTEM`) with 3 compacted PDF-page passages; gold page at a random rank among BM25 distractors | Model learns to find and cite the right `[S#]` |
| Target | Short answer, every fact cited `[S#]`, caveats for preliminary data and projections, final `Sources:` line; the exact abstention sentence when the answer is absent | The behaviour experiment 01 lacked |
| Loss | Assistant answer tokens only | Don't train the model to reproduce passages |
| Deployment | LoRA adapter layered on the same `llama3.1:8b` via an Ollama Modelfile `ADAPTER` (merged Q4_K_M GGUF as fallback) | Base weights, quantization and template are identical across arms |
| Test set | The 9 experiment-01 questions, unchanged | Held out from training |

### Contamination guards (enforced by `bls_rag.finetune_data` and tests)

- No training context contains any experiment-01 gold reference page
  (D1 p9, D2 p11, and page 1 of D3–D8).
- No training question duplicates an evaluation question, and no training
  answer restates an evaluation answer (e.g. no Washington annual or December
  seasonally adjusted rate, no headline payroll, JOLTS or projection totals).
- Every number in a training answer is checked against the gold excerpt
  (`check` strings), so the model is never trained to state a figure the
  passage doesn't show.

### Finding while building the data

`page_excerpt` (unchanged from experiment 01) keeps the line that best matches
the question. On long national tables (e.g. D3 p9, OEWS Table 1) the table
**title** outscores the requested occupation row, so the row can be cut from
the 5,000-character excerpt. Two planned examples (data scientists, software
developers) failed the check for that reason and were replaced. Retrieval is
deliberately left unchanged so this experiment isolates the effect of
fine-tuning, but it's a candidate fix for a later retrieval experiment.

## Steps

```powershell
# 1. Dataset (any OS; no GPU, no model calls). Writes data/train.jsonl
uv run python -m bls_rag.finetune_data

# 2. Train and export: see ../../finetune/README.md (WSL2 + GPU)

# 3. Register the fine-tuned model with Ollama (Windows)
ollama create llama3.1-bls-ft -f finetune\outputs\bls-ft\Modelfile

# 4. Freeze and run the four arms once (base/ft × RAG/closed-book)
uv run bls-rag ingest                 # if index/ is missing
uv run bls-rag experiment freeze experiments/02_finetune
uv run bls-rag experiment run    experiments/02_finetune

# 5. Score manually against the PDFs using ../01_rag_eval/scoring_rubric.md
uv run python -m bls_rag.evaluation.finetune_scoring template
uv run python -m bls_rag.evaluation.judge_ui      # grading page; fills artifacts/judgments.json as you go
uv run python -m bls_rag.evaluation.finetune_scoring summary
```

The grading page (http://127.0.0.1:8010) shows one question at a time: the
reference answer, required criteria and evidence on the left, the four answers
on the right. Arms are hidden and shuffled by default so grading is blind.
It is keyboard-driven (`2`/`1`/`0` score, `A` abstained, `Y`/`N` citations,
`Enter` next ungraded) and saves every change. As an aid, it colours each
figure in an answer by whether it appears in the reference, and lists which
of the given pages actually shows it next to the pages the answer cited. The
judgment itself stays manual. `--judgments copy.json` grades a separate copy
(for a second grader).

`summary` also reports automatic format compliance per arm (has `[S#]`,
citations in range, `Sources:` line, exact abstention sentence), plus mean
latency and output tokens.

## Cost-benefit inputs

Dataset size: 44 examples ≈ 93k tokens, so 3 epochs ≈ 280k training tokens
(rough estimate; `train.py` prints exact counts).

| Option | Training cost for this dataset | Inference | Notes |
|---|---|---|---|
| Local QLoRA (this repo) | ~$0 cash; minutes of laptop-GPU time (`train_summary.json` records it) | Local Ollama, same speed as base | Needs a CUDA GPU and WSL2 setup; data stays local |
| Together AI LoRA SFT, Llama 3.1 8B | $0.34 per 1M training tokens, $4.00 minimum per job, so this dataset pays the **$4 minimum** | Hosted per-token or dedicated endpoint | No GPU needed; weights downloadable |
| OpenAI SFT (gpt-4.1-mini) | Reported at about $5.00 per 1M training tokens, so about $1.40 | Fine-tuned inference reported at $0.80 in / $3.20 out per 1M | Different, closed model, so not comparable to this Llama baseline. The model is marked deprecated |
| Prompt engineering only | $0 | Unchanged | Cheapest. Should be tried first; see reflection |
| Fix retrieval/excerpting | $0 | Unchanged | Addresses failures fine-tuning can't (missing rows) |

Prices checked November 2026 and change often, so verify before citing:
Together AI pricing page (via [developersdigest summary](https://www.developersdigest.tech/models/fine-tuning/together-ai));
OpenAI fine-tuning rates as summarised by [developersdigest](https://www.developersdigest.tech/models/fine-tuning/openai);
[gpt-4.1-mini model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini) (deprecation status).

Expect the dominant cost to be **human time**: every example has to be written
and checked against the PDFs, and that work grows with the dataset, while the
training compute stays near zero. Record the hours actually spent alongside
`train_summary.json`; it is the main input to "is it worth it?"

## Reflection (fill in after scoring)

One page, covering:

1. What changed between base + RAG and ft + RAG (correctness, citation support, format compliance, abstentions on B9).
2. Whether closed-book scores moved. Little change is evidence that fine-tuning changed behaviour, not knowledge.
3. Which experiment-01 failures were fixed, which weren't, and why (e.g. a row missing from the excerpt can't be fixed by fine-tuning).
4. When fine-tuning is worth it vs prompting/RAG for this domain, using the cost table above and the measured gains.
5. Limits: n=9 test questions, single run, one grader, development-set reuse.
