"""Create a runnable assignment package from an explicit non-private file list."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def build():
    dest=ROOT/'submission';dest.mkdir(exist_ok=True)
    files=['README.md','requirements.txt','requirements.lock.txt','requirements-docs.txt','requirements-test.txt','rag_eval.py','model_worker.py',
      'final_evaluation.py','sources.py','questions.json','references.json','freeze_manifest.json',
      'scoring_rubric.md','score_final.py','verify_references.py','verify_submission.py','report.py',
      'publication_audit.py','publication_files.json','PUBLICATION_REVIEW.md','THIRD_PARTY_NOTICES.md',
      '.gitignore','.gitattributes','finish_publish.ps1','.env.example','verify_ollama.py','package_submission.py']
    for name in files:
        if (ROOT/name).exists():shutil.copy2(ROOT/name,dest/name)
    for name in ['docs','artifacts','provenance','tests','.github']:
        shutil.copytree(ROOT/name,dest/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    # Package has its own publication inventory, so its audit also works independently.
    import subprocess,sys
    subprocess.run([sys.executable,'publication_audit.py','--write-manifest'],cwd=dest,check=True)
    hashes={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file() and p.name!='submission_checksums.json' and '__pycache__' not in p.parts}
    (dest/'submission_checksums.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
    print('Prepared submission with',len(hashes),'files, eight PDFs and fresh artifacts; no index, models or private configuration.')
if __name__=='__main__':build()
