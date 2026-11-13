"""Check that the experiment-01 runtime code at the submission-v1 tag matches its freeze.

Requires Git history (a full clone, or `git fetch --tags`). No model calls.
"""
import hashlib
import json
import subprocess
import sys

from bls_rag.paths import FROZEN_AT_TAG, LEGACY_RUNTIME_FILES, RAG_EVAL_DIR, ROOT


def main() -> int:
    frozen = json.loads((RAG_EVAL_DIR / 'freeze_manifest.json').read_text(encoding='utf-8'))['hashes']
    for name in sorted(LEGACY_RUNTIME_FILES):
        blob = subprocess.run(['git', 'show', f'{FROZEN_AT_TAG}:{name}'], cwd=ROOT,
                              capture_output=True, check=True).stdout
        if hashlib.sha256(blob).hexdigest() != frozen[name]:
            print(f'MISMATCH {name} at {FROZEN_AT_TAG}', file=sys.stderr)
            return 1
        print(f'OK {name} at {FROZEN_AT_TAG}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
