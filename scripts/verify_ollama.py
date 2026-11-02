"""Verify the configured installed model through the application's local path."""
import json
from datetime import datetime, timezone

import rag_eval as rag


def main():
    report = {'provider': 'ollama', 'settings': rag.config()}
    try:
        report['model_identity'] = rag.model_identity()
        report['server_version'] = rag.ollama_json('/api/version')
        model = rag.get_llm()
        report['answer'] = rag.invoke_model(model, 'Reply with only OK.', 'Confirm local generation works.')
        report['call'] = model.last_call
        report['loaded_models'] = rag.ollama_json('/api/ps')
        report['status'] = 'completed'
    except Exception as exc:
        report['status'] = 'failed'
        report['exception_type'] = type(exc).__name__
        report['failure_category'] = getattr(exc, 'category', 'setup_failure')
    rag.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = rag.RESULTS_DIR / f'verification_{stamp}.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print('Evidence:', output)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
