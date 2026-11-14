"""QLoRA fine-tune of Llama 3.1 8B Instruct on the experiment-02 dataset (Unsloth).

Runs on a single 8 GB NVIDIA GPU under WSL2. Always start with a smoke test:

    uv run train.py --smoke-test     # 5 steps on the longest example, prints peak VRAM
    uv run train.py                  # full run, saves the LoRA adapter

Prompts are rendered with exactly the Llama 3.1 chat format that Ollama's
``llama3.1:8b`` template produces (no injected date lines), and loss is computed
on the assistant answer only, so the model learns how to answer, not to
reproduce the passages.
"""
from __future__ import annotations

import argparse
import inspect
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'experiments' / '02_finetune' / 'data' / 'train.jsonl'
BASE = 'unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit'

USER_HEADER = '<|start_header_id|>user<|end_header_id|>\n\n'
ASSISTANT_HEADER = '<|start_header_id|>assistant<|end_header_id|>\n\n'


def render(messages: list[dict]) -> str:
    """Llama 3.1 chat text as Ollama renders it; the tokenizer adds <|begin_of_text|>."""
    text = ''
    for m in messages:
        role = {'system': 'system', 'user': 'user', 'assistant': 'assistant'}[m['role']]
        text += f'<|start_header_id|>{role}<|end_header_id|>\n\n{m["content"]}<|eot_id|>'
    return text


def _sft_config(SFTConfig, **kwargs):
    """Pass max length under whichever name the installed TRL uses."""
    params = inspect.signature(SFTConfig.__init__).parameters
    length = kwargs.pop('max_length')
    kwargs['max_length' if 'max_length' in params else 'max_seq_length'] = length
    return SFTConfig(**{k: v for k, v in kwargs.items() if k in params})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--output', type=Path, default=HERE / 'outputs' / 'bls-ft')
    parser.add_argument('--base-model', default=BASE)
    parser.add_argument('--max-seq-length', type=int, default=4096)
    parser.add_argument('--epochs', type=float, default=3)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--rank', type=int, default=16)
    parser.add_argument('--grad-accum', type=int, default=8)
    parser.add_argument('--seed', type=int, default=3407)
    parser.add_argument('--smoke-test', action='store_true', help='5 steps on the longest example only')
    args = parser.parse_args()

    import torch
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import train_on_responses_only

    if not torch.cuda.is_available():
        raise SystemExit('No CUDA GPU visible. In WSL2, check `nvidia-smi` works first.')
    gpu = torch.cuda.get_device_properties(0)
    print(f'GPU: {gpu.name}, {gpu.total_memory / 2**30:.1f} GiB')

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model, max_seq_length=args.max_seq_length, dtype=None, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(
        model, r=args.rank, lora_alpha=args.rank, lora_dropout=0, bias='none',
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
        use_gradient_checkpointing='unsloth', random_state=args.seed)

    rows = [json.loads(line) for line in args.data.read_text(encoding='utf-8').splitlines() if line.strip()]
    texts = [render(r['messages']) for r in rows]
    lengths = [len(tokenizer(t).input_ids) for t in texts]
    print(f'{len(rows)} examples; tokens min/median/max = {min(lengths)}/{sorted(lengths)[len(lengths) // 2]}/{max(lengths)}')
    too_long = [r['id'] for r, n in zip(rows, lengths) if n > args.max_seq_length]
    if too_long:
        raise SystemExit(f'Examples exceed --max-seq-length {args.max_seq_length}: {too_long}. '
                         'Rebuild with fewer --pages or a lower --max-page-chars.')
    if args.smoke_test:
        longest = max(range(len(texts)), key=lengths.__getitem__)
        texts = [texts[longest]] * 8
        print(f'Smoke test on {rows[longest]["id"]} ({lengths[longest]} tokens)')

    trainer = SFTTrainer(
        model=model,
        **({'processing_class': tokenizer} if 'processing_class' in inspect.signature(SFTTrainer.__init__).parameters
           else {'tokenizer': tokenizer}),
        train_dataset=Dataset.from_dict({'text': texts}),
        args=_sft_config(
            SFTConfig, dataset_text_field='text', max_length=args.max_seq_length, packing=False,
            per_device_train_batch_size=1, gradient_accumulation_steps=1 if args.smoke_test else args.grad_accum,
            num_train_epochs=args.epochs, max_steps=5 if args.smoke_test else -1,
            learning_rate=args.lr, warmup_steps=2, lr_scheduler_type='linear', weight_decay=0.01,
            optim='adamw_8bit', logging_steps=1, seed=args.seed, report_to='none',
            output_dir=str(args.output / 'checkpoints'), save_strategy='no'),
    )
    trainer = train_on_responses_only(trainer, instruction_part=USER_HEADER, response_part=ASSISTANT_HEADER)

    torch.cuda.reset_peak_memory_stats()
    started = time.time()
    stats = trainer.train()
    peak = torch.cuda.max_memory_reserved() / 2**30
    summary = {'smoke_test': args.smoke_test, 'base_model': args.base_model, 'examples': len(rows),
               'max_tokens': max(lengths), 'max_seq_length': args.max_seq_length, 'epochs': args.epochs,
               'lr': args.lr, 'rank': args.rank, 'grad_accum': args.grad_accum, 'seed': args.seed,
               'train_seconds': round(time.time() - started, 1), 'train_loss': stats.training_loss,
               'peak_vram_gib': round(peak, 2), 'gpu': gpu.name,
               'gpu_total_gib': round(gpu.total_memory / 2**30, 2),
               'loss_history': [h['loss'] for h in trainer.state.log_history if 'loss' in h]}
    print(json.dumps(summary, indent=2))
    if args.smoke_test:
        print(f'Smoke test passed: peak {peak:.2f} GiB of {gpu.total_memory / 2**30:.1f}. Run without --smoke-test.')
        return
    adapter = args.output / 'adapter'
    model.save_pretrained(str(adapter))
    tokenizer.save_pretrained(str(adapter))
    (args.output / 'train_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'Saved LoRA adapter to {adapter}. Next: uv run export.py')


if __name__ == '__main__':
    main()
