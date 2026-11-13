"""Offline verification of the frozen experiment-01 evidence in the current layout.

Every data file recorded in ``freeze_manifest.json`` is re-hashed at its new
location. The frozen *runtime code* was refactored into this package, so its
original bytes are verified at the ``submission-v1`` tag instead (see
``scripts/verify_frozen_tag.py`` or the release ZIP). Local index files are
reported as omitted unless ``--live`` is given.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

from pypdf import PdfReader

from bls_rag.evaluation.references import normalized
from bls_rag.paths import CORPUS_DIR, FROZEN_AT_TAG, PDF_DIR, RAG_EVAL_DIR, ROOT, legacy_path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root: Path, name: str) -> Path:
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe manifest path')
    target = root.joinpath(*p.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path leaves package')
    return target


def check_hashes(root: Path, checks: dict, require_assets: bool = False, resolve=None):
    """Verify ``{name: sha256}``. ``resolve`` maps a recorded name to a path (or None = at tag)."""
    count, omitted, at_tag = 0, [], []
    for name, expected in checks.items():
        safe_path(root, name)
        p = resolve(name) if resolve else root / name
        if p is None:
            at_tag.append(name)
            continue
        if not p.is_file():
            if name.startswith('index/') and not require_assets:
                omitted.append(name)
                continue
            raise ValueError('Required file missing: ' + name)
        if sha256(p) != expected:
            raise ValueError('Hash mismatch: ' + name)
        count += 1
    return count, omitted, at_tag


def verify_experiment(require_assets: bool = False) -> dict:
    exp = RAG_EVAL_DIR
    frozen = json.loads((exp / 'freeze_manifest.json').read_text(encoding='utf-8'))
    verified, omitted, at_tag = check_hashes(ROOT, frozen['hashes'], require_assets, legacy_path)

    inv = json.loads((CORPUS_DIR / 'source_inventory.json').read_text(encoding='utf-8'))['documents']
    pdfs = {p.name for p in PDF_DIR.glob('*.pdf')}
    if len(inv) != 8 or pdfs != {r['filename'] for r in inv}:
        raise ValueError('Exactly eight registered PDFs required')
    for r in inv:
        if sha256(PDF_DIR / r['filename']) != r['sha256'] or sha256(CORPUS_DIR / r['html_snapshot']) != r['html_sha256']:
            raise ValueError('Source provenance mismatch')
        if not r['release_date'] or not r['retrieved_utc'] or 'bls.gov/opub/copyright' not in r['reuse_terms_url']:
            raise ValueError('Missing source/reuse metadata')

    questions = json.loads((exp / 'questions.json').read_text(encoding='utf-8'))
    refs = json.loads((exp / 'references.json').read_text(encoding='utf-8'))
    ids = {q['id'] for q in questions}
    if len(questions) != 9 or len(ids) != 9 or ids != {r['id'] for r in refs}:
        raise ValueError('Question/reference count mismatch')
    answerable = [r for r in refs if r['answerability'] == 'answerable']
    if len(answerable) != 8:
        raise ValueError('Eight answerable cases plus one abstention required')
    if {e['filename'] for r in answerable for e in r['evidence']} != pdfs:
        raise ValueError('Each PDF must support a reference')
    for ref in answerable:
        for e in ref['evidence']:
            text = normalized(PdfReader(PDF_DIR / e['filename']).pages[e['pdf_page'] - 1].extract_text())
            cursor = 0
            for line in e['supporting_excerpt'].splitlines():
                needle = normalized(line)
                pos = text.find(needle, cursor)
                if pos < 0:
                    raise ValueError('PDF reference excerpt mismatch: ' + ref['id'])
                cursor = pos + len(needle)

    raw = exp / 'artifacts' / 'final_evaluation.jsonl'
    rows = [json.loads(x) for x in raw.read_text(encoding='utf-8').splitlines()]
    if len(rows) != 9 or {r['id'] for r in rows} != ids:
        raise ValueError('Paired output count mismatch')
    for r in rows:
        if (r['freeze_sha256'] != sha256(exp / 'freeze_manifest.json') or r['settings'] != frozen['settings']
                or r['model_identity'] != frozen['model_identity']):
            raise ValueError('Paired frozen input/settings mismatch')
    judgments = json.loads((exp / 'artifacts' / 'scoring_judgments.json').read_text(encoding='utf-8'))
    if judgments['raw_sha256'] != sha256(raw):
        raise ValueError('Manual judgment binding mismatch')
    summary = json.loads((exp / 'artifacts' / 'summary.json').read_text(encoding='utf-8'))
    if (summary['questions'] != 9 or summary['documents'] != 8 or summary['answerable'] != 8
            or summary['k'] != 4 or summary['old_scores_reused']):
        raise ValueError('Summary denominator/unit mismatch')
    return {'documents': 8, 'questions': 9, 'answerable': 8, 'paired_cases': 9,
            'verified_frozen_files': verified, 'omitted_local_indexes': omitted,
            'runtime_code_verified_at_tag': {'tag': FROZEN_AT_TAG, 'files': at_tag},
            'pdf_references_verified': 8, 'retrieval_unit': 'PDF page', 'k': 4}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--live', action='store_true', help='Also require the local index files')
    args = parser.parse_args(argv)
    print(json.dumps(verify_experiment(args.live), indent=2))
    print('PASS offline source, freeze, paired-record and reference validation (no model calls)')


if __name__ == '__main__':
    main()
