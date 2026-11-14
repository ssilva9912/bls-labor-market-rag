"""Smoke-test a local Ollama model through the application's bounded call path.

Usage: uv run python -m scripts.verify_ollama [MODEL]
"""
import json
import sys

from bls_rag import generation
from bls_rag.config import config


def main() -> int:
    settings = config(**({'chat_model': sys.argv[1]} if len(sys.argv) > 1 else {}))
    report = {'model': settings['chat_model']}
    try:
        report['model_identity'] = generation.model_identity(settings)
        report['server_version'] = generation.ollama_json('/api/version', settings=settings)
        model = generation.get_llm(settings)
        report['answer'] = generation.invoke_model(model, 'Reply with only OK.', 'Confirm local generation works.')
        report['call'] = model.last_call
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='failed', exception_type=type(exc).__name__,
                      failure_category=getattr(exc, 'category', 'setup_failure'))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
