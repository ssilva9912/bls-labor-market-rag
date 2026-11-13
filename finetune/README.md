# Local QLoRA training (WSL2 + NVIDIA GPU)

A separate uv project so the CUDA training stack (torch, Unsloth, TRL,
bitsandbytes) never touches the main RAG environment. Linux only: use WSL2 on
Windows. Sized for an 8 GB laptop GPU (RTX 4070 Laptop).

## One-time setup (WSL2 Ubuntu)

```bash
nvidia-smi                       # must list the GPU (uses the Windows NVIDIA driver; don't install a Linux driver)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Work on the Windows checkout, but keep the training venv on the Linux filesystem (much faster)
cd /mnt/c/path/to/bls-labor-market-rag/finetune
export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/bls-ft
uv sync                          # locked: unsloth, torch (CUDA), trl, peft, bitsandbytes
```

The first run downloads `unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit`
(about 5.7 GB) into `~/.cache/huggingface`.

## Train

The dataset is built from the repo root on Windows or WSL: `uv run python -m bls_rag.finetune_data`.

```bash
uv run train.py --smoke-test     # 5 steps on the longest example; prints peak VRAM
uv run train.py                  # full run (~44 examples × 3 epochs), saves outputs/bls-ft/adapter
uv run export.py                 # writes outputs/bls-ft/Modelfile (FROM llama3.1:8b + ADAPTER) and ollama_adapter/
```

`export.py` copies the adapter to `outputs/bls-ft/ollama_adapter/` with the
weights renamed to `model.safetensors`, because `ollama create` does not pick
up PEFT's `adapter_model.safetensors` name. If you trained in a WSL clone, copy
`outputs/bls-ft/` into the Windows checkout first (it is git-ignored).

Then in Windows PowerShell, from the repo root:

```powershell
ollama create llama3.1-bls-ft -f finetune\outputs\bls-ft\Modelfile
uv run python -m scripts.verify_ollama llama3.1-bls-ft
```

## If it runs out of memory

Close anything else using the GPU (browsers, games) and try these in order:

1. Shorter examples: `uv run python -m bls_rag.finetune_data --max-page-chars 2800` (repo root), then retrain.
2. `uv run train.py --max-seq-length 3072` (the script refuses if any example is longer).
3. Two passages per example: `--pages 2` when building the dataset.

Don't switch to a smaller base model. The comparison only means something if
base and fine-tuned share the same 8B weights.

## Outputs (git-ignored)

`outputs/bls-ft/adapter/` holds the LoRA weights (on the order of 100–200 MB) and
`train_summary.json` records loss, time and peak VRAM. Copy
`train_summary.json` into `experiments/02_finetune/artifacts/` for the report.
The assignment's "fine-tuned model" deliverable is the adapter: attach it to a
GitHub release rather than committing it.

## Adapter vs merged GGUF

Ollama's docs warn that adapters trained on a differently quantized base (as
QLoRA is) can behave erratically. Sanity-check a couple of the training
questions with `uv run bls-rag ask "..." --model llama3.1-bls-ft` first. If the
answers look garbled or ignore the trained format, use `uv run export.py --gguf`.
It merges the adapter into 16-bit weights and quantizes to a standalone Q4_K_M
GGUF (needs ~16 GB free disk), and you then `ollama create` from that Modelfile
instead. Record which path you used in the experiment report.
