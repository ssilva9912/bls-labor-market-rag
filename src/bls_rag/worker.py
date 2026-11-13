"""One local Ollama generation call; stdout contains text-only JSON.

Run as ``python -m bls_rag.worker`` by :class:`bls_rag.generation.BoundedChatModel`.
"""
import json
import sys

from bls_rag import generation


def safe_error_payload(exc):
    name = type(exc).__name__
    category = 'ollama_failure'
    if 'timeout' in name.lower():
        category = 'transport_timeout'
    elif 'connect' in name.lower() or 'network' in name.lower():
        category = 'connection_failure'
    payload = {'error_category': category, 'exception_type': name}
    code = getattr(exc, 'status_code', None)
    if isinstance(code, int):
        payload['http_status'] = code
    return payload


def main():
    try:
        request = json.load(sys.stdin)
        model = generation.create_ollama_llm(request.get('settings'))
        message = model.invoke(request['messages'])
        metadata = message.response_metadata
        reason = str(metadata.get('done_reason', 'stop')).lower()
        answer = generation.response_text(message.content)
        metrics = {k: metadata[k] for k in ('model', 'total_duration', 'load_duration',
                   'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration')
                   if isinstance(metadata.get(k), (int, float, str))}
        payload = {'finish_reason': reason, 'ollama_metrics': metrics}
        if reason == 'length':
            payload['error_category'] = 'truncated_response'
        elif not answer.strip():
            payload['error_category'] = 'empty_response'
        else:
            payload['answer'] = answer
    except Exception as exc:
        payload = safe_error_payload(exc)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
