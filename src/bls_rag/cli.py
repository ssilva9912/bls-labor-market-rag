"""Command line: ``uv run bls-rag <command>``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bls_rag.config import config
from bls_rag.paths import PDF_DIR


def _ask(args) -> None:
    from bls_rag import generation, index, retrieval
    settings = config(**({'chat_model': args.model} if args.model else {}))
    llm = generation.get_llm(settings)
    if args.no_retrieval:
        print('\n' + generation.answer_baseline(llm, args.question))
        return
    chunks = retrieval.retrieve(args.question, index.load_chroma(), args.retrieval,
                                settings['top_k'], settings['candidate_k'])
    print('\n' + generation.answer_rag(llm, args.question, chunks))
    print('\nRETRIEVED EVIDENCE:')
    for c in chunks:
        print(f' [S{c["rank"]}] {c["source"]}, p. {c["page"]}')
        print('    ' + c['content'][:250].replace('\n', ' ') + '...')


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog='bls-rag', description='Local RAG over eight official BLS reports')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('ingest', help='Rebuild the local Chroma index from the corpus PDFs')
    p.add_argument('--docs', type=Path, default=PDF_DIR)

    p = sub.add_parser('ask', help='Answer one question, showing retrieved pages')
    p.add_argument('question')
    p.add_argument('--model', help='Ollama model name (default: OLLAMA_MODEL or llama3.1:8b)')
    p.add_argument('--retrieval', choices=['hybrid', 'dense'], default=config()['retrieval_mode'])
    p.add_argument('--no-retrieval', action='store_true', help='Closed-book answer without documents')

    p = sub.add_parser('corpus', help='Verify (offline) or download the BLS corpus')
    p.add_argument('action', choices=['verify', 'download'])

    p = sub.add_parser('experiment', help='Freeze, validate or run an experiment directory once')
    p.add_argument('action', choices=['freeze', 'validate', 'run'])
    p.add_argument('directory', type=Path)

    sub.add_parser('verify', help='Offline verification of the frozen experiment-01 evidence')

    args = parser.parse_args(argv)
    if args.command == 'ingest':
        from bls_rag.index import ingest
        ingest(args.docs)
    elif args.command == 'ask':
        _ask(args)
    elif args.command == 'corpus':
        from bls_rag import corpus
        print('Verified', corpus.verify(), 'PDFs and provenance offline.') if args.action == 'verify' else corpus.download()
    elif args.command == 'experiment':
        from bls_rag import experiment
        experiment.main([args.action, str(args.directory)])
    elif args.command == 'verify':
        from bls_rag.evaluation import verify
        verify.main([])


def entrypoint() -> None:
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    entrypoint()
