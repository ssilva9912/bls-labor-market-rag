"""Package the trained LoRA adapter for Ollama.

Default (recommended): a Modelfile that layers the safetensors adapter on the
exact ``llama3.1:8b`` you already run, so the base weights, quantization,
chat template and stop tokens are identical for the base and fine-tuned arms:

    uv run export.py
    ollama create llama3.1-bls-ft -f outputs/bls-ft/Modelfile

Fallback (``--gguf``): merge the adapter and write a standalone Q4_K_M GGUF.
Use it only if your Ollama version rejects the ADAPTER line; it needs ~16 GB
of free disk and builds llama.cpp on first use.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_OLLAMA = 'llama3.1:8b'


def base_modelfile() -> str | None:
    """The base model's Modelfile (template, stop tokens), from Windows or WSL Ollama."""
    for exe in ('ollama', 'ollama.exe'):
        if shutil.which(exe):
            result = subprocess.run([exe, 'show', BASE_OLLAMA, '--modelfile'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', type=Path, default=HERE / 'outputs' / 'bls-ft')
    parser.add_argument('--gguf', action='store_true', help='Merge and quantize to a standalone Q4_K_M GGUF')
    parser.add_argument('--name', default='llama3.1-bls-ft')
    args = parser.parse_args()
    adapter = args.run / 'adapter'
    if not (adapter / 'adapter_config.json').exists():
        raise SystemExit(f'No adapter at {adapter}; run train.py first.')

    if not args.gguf:
        modelfile = f'FROM {BASE_OLLAMA}\nADAPTER ./adapter\n'
    else:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(str(adapter), max_seq_length=8192, load_in_4bit=True)
        target = args.run / 'gguf'
        model.save_pretrained_gguf(str(target), tokenizer, quantization_method='q4_k_m')
        gguf = sorted(args.run.rglob('*Q4_K_M*.gguf'), key=lambda p: p.stat().st_mtime)[-1]
        base = base_modelfile()
        if base is None:
            raise SystemExit(f'Wrote {gguf}, but could not read the base Modelfile. Run '
                             f'`ollama show {BASE_OLLAMA} --modelfile`, replace its FROM line with '
                             f'FROM ./{gguf.relative_to(args.run).as_posix()} and save it as {args.run}/Modelfile.')
        lines = [ln for ln in base.splitlines() if not ln.startswith('FROM ')]
        modelfile = f'FROM ./{gguf.relative_to(args.run).as_posix()}\n' + '\n'.join(lines) + '\n'

    (args.run / 'Modelfile').write_text(modelfile, encoding='utf-8')
    print(f'Wrote {args.run / "Modelfile"}')
    print(f'Next (where Ollama runs): ollama create {args.name} -f {args.run / "Modelfile"}')


if __name__ == '__main__':
    main()
