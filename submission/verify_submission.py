"""Offline validation of the eight-PDF assignment and its submission package."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess
import sys
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def safe_path(root,name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe manifest path')
    target=root.joinpath(*p.parts)
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('Path leaves package')
    return target
def check_hashes(root,checks,require_assets=False):
    count=0;omitted=[]
    for name,expected in checks.items():
        p=safe_path(root,name)
        if not p.is_file():
            if name.startswith('index/') and not require_assets:omitted.append(name);continue
            raise ValueError('Required file missing: '+name)
        if sha256(p)!=expected:raise ValueError('Hash mismatch: '+name)
        count+=1
    return count,omitted
def verify_package(root,require_assets=False):
    frozen=json.loads((root/'freeze_manifest.json').read_text(encoding='utf-8'))
    verified,omitted=check_hashes(root,frozen['hashes'],require_assets)
    inv=json.loads((root/'docs/source_inventory.json').read_text(encoding='utf-8'))['documents']
    pdfs={p.name for p in (root/'docs').glob('*.pdf')}
    if len(inv)!=8 or pdfs!={r['filename'] for r in inv}:raise ValueError('Exactly eight registered PDFs required')
    for r in inv:
        if sha256(root/'docs'/r['filename'])!=r['sha256'] or sha256(root/r['html_snapshot'])!=r['html_sha256']:
            raise ValueError('Source provenance mismatch')
        if not r['release_date'] or not r['retrieved_utc'] or 'bls.gov/opub/copyright' not in r['reuse_terms_url']:
            raise ValueError('Missing source/reuse metadata')
    questions=json.loads((root/'questions.json').read_text(encoding='utf-8'))
    refs=json.loads((root/'references.json').read_text(encoding='utf-8'))
    ids={q['id'] for q in questions}
    if len(questions)!=9 or len(ids)!=9 or ids!={r['id'] for r in refs}:raise ValueError('Question/reference count mismatch')
    answerable=[r for r in refs if r['answerability']=='answerable']
    if len(answerable)!=8:raise ValueError('Eight answerable cases plus one abstention required')
    if {e['filename'] for r in answerable for e in r['evidence']}!=pdfs:raise ValueError('Each PDF must support a reference')
    from verify_references import normalized
    for ref in answerable:
        for e in ref['evidence']:
            text=normalized(PdfReader(root/'docs'/e['filename']).pages[e['pdf_page']-1].extract_text())
            cursor=0
            for line in e['supporting_excerpt'].splitlines():
                needle=normalized(line);pos=text.find(needle,cursor)
                if pos<0:raise ValueError('PDF reference excerpt mismatch: '+ref['id'])
                cursor=pos+len(needle)
    raw=root/'artifacts/final_evaluation.jsonl'
    rows=[json.loads(x) for x in raw.read_text(encoding='utf-8').splitlines()]
    if len(rows)!=9 or {r['id'] for r in rows}!=ids:raise ValueError('Paired output count mismatch')
    for r in rows:
        if r['freeze_sha256']!=sha256(root/'freeze_manifest.json') or r['settings']!=frozen['settings'] or r['model_identity']!=frozen['model_identity']:
            raise ValueError('Paired frozen input/settings mismatch')
    judgments=json.loads((root/'artifacts/scoring_judgments.json').read_text(encoding='utf-8'))
    if judgments['raw_sha256']!=sha256(raw):raise ValueError('Manual judgment binding mismatch')
    summary=json.loads((root/'artifacts/summary.json').read_text(encoding='utf-8'))
    if summary['questions']!=9 or summary['documents']!=8 or summary['answerable']!=8 or summary['k']!=4 or summary['old_scores_reused']:
        raise ValueError('Summary denominator/unit mismatch')
    if (root/'submission_checksums.json').exists():
        check_hashes(root,json.loads((root/'submission_checksums.json').read_text(encoding='utf-8')),require_assets)
    return {'documents':8,'questions':9,'answerable':8,'paired_cases':9,'verified_frozen_files':verified,'omitted_local_indexes':omitted,
            'pdf_references_verified':8,'retrieval_unit':'PDF page','k':4}
def main():
    parser=argparse.ArgumentParser(__doc__);group=parser.add_mutually_exclusive_group();group.add_argument('--offline',action='store_true');group.add_argument('--live',action='store_true');parser.add_argument('--package',type=Path)
    args=parser.parse_args();root=args.package.resolve() if args.package else ROOT
    print(json.dumps(verify_package(root,args.live),indent=2))
    if args.live:subprocess.run([sys.executable,'final_evaluation.py','validate'],cwd=root,check=True)
    else:print('SKIP live Ollama identity, generation, embeddings and Chroma retrieval: offline validation makes no model calls or downloads. PDFs and reference excerpts ARE verified.')
    print('PASS offline source, freeze, paired-record and reference validation')
if __name__=='__main__':main()
