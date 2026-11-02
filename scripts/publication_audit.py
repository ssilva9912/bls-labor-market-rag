"""Audit intended/tracked publication paths; never print credential matches."""
import argparse,json,re,subprocess,shutil,tempfile,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'.gitignore','.gitattributes','.env.example','README.md','requirements.txt','requirements.lock.txt','requirements-docs.txt','requirements-test.txt',
 'rag_eval.py','model_worker.py','final_evaluation.py','sources.py','verify_references.py','score_final.py',
 'verify_submission.py','verify_ollama.py','report.py','package_submission.py','publication_audit.py',
 'questions.json','references.json','freeze_manifest.json','scoring_rubric.md',
 'PUBLICATION_REVIEW.md','THIRD_PARTY_NOTICES.md','publication_files.json','submission_checksums.json','finish_publish.ps1'}
def permitted(name):
    p=Path(name)
    if p.name.startswith('~$'):return False
    if any(part in {'archive','tmp','index','results','__pycache__','.git','.uv-cache','.uv-python','.cache','.ollama','models'} or part.startswith('.venv') for part in p.parts):return False
    if p.name.startswith('.env') and name not in {'.env.example','submission/.env.example'}:return False
    if 'credential' in p.name.lower() or 'service-account' in p.name.lower():return False
    if p.suffix.lower() in {'.key','.pem','.gguf','.safetensors','.sqlite3','.db','.pyc','.zip'}:return False
    if p.suffix.lower()=='.pdf':
        if p.parent.name=='docs':
            inventory=ROOT/'docs/source_inventory.json'
            return inventory.exists() and p.name in {r['filename'] for r in json.loads(inventory.read_text())['documents']}
        return p.name=='reflection.pdf' and p.parent.name=='artifacts'
    if name in ROOT_FILES or name=='.github/workflows/ci.yml':return True
    if p.parts[0] in {'scripts','evaluation'}:return p.suffix in {'.py','.ps1'}
    if p.parts[0]=='tests':return p.suffix=='.py'
    if p.parts[0]=='docs':
        if name=='docs/source_inventory.json':return True
        inventory=ROOT/'docs/source_inventory.json'
        return inventory.exists() and p.name in {r['filename'] for r in json.loads(inventory.read_text())['documents']}
    if p.parts[0]=='artifacts':return p.suffix in {'.md','.csv','.json','.jsonl','.pdf','.docx'}
    if p.parts[0]=='provenance':return p.suffix in {'.json','.md','.htm'}
    if p.parts[0]=='submission':return p.suffix in {'.py','.ps1','.md','.json','.jsonl','.csv','.pdf','.docx','.htm','.txt','.yml'} or p.name in {'.gitignore','.gitattributes','.env.example'}
    return False
PATTERNS={'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 'google_api_key':re.compile(r'AIza[0-9A-Za-z_-]{35}'),
 'github_token':re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
 'aws_access_key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
 'openai_key':re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}'),
 'literal_secret_assignment':re.compile(r'''(?im)^\s*(?:[A-Z_]*(?:API_KEY|ACCESS_TOKEN|CLIENT_SECRET|PASSWORD))\s*=\s*["']?[A-Za-z0-9_+/=-]{20,}''')}
def candidates():return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and permitted(p.relative_to(ROOT).as_posix()))
def publication_text(path):
    """Use strict supported decoders and document readers; never discard bytes."""
    import zipfile
    import xml.etree.ElementTree as ET
    data=path.read_bytes()
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(path,strict=True)
        if reader.is_encrypted:raise ValueError('Encrypted PDF')
        return '\n'.join(page.extract_text() for page in reader.pages)
    if path.suffix.lower()=='.docx':
        with zipfile.ZipFile(path) as doc:
            if 'word/document.xml' not in doc.namelist():raise ValueError('Invalid DOCX')
            parts=[]
            for name in doc.namelist():
                if name.endswith(('.xml','.rels')):
                    raw=doc.read(name).decode('utf-8-sig')
                    parts.extend([raw, ''.join(ET.fromstring(raw).itertext())])
            return '\n'.join(parts)
    if data.startswith((b'\xff\xfe',b'\xfe\xff')):return data.decode('utf-16')
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        # Legacy BLS HTML uses Windows-1252 punctuation. Restrict fallback
        # to actual HTML; arbitrary unreadable files must fail closed.
        if path.suffix.lower() not in {'.htm','.html'}:raise
        text=data.decode('cp1252')
        if not re.match(r'\s*<!doctype html',text,re.I):raise ValueError('Invalid HTML')
        return text

def audit(paths):
    findings=[]
    for name in paths:
        if not permitted(name):findings.append({'path':name,'category':'excluded_path'});continue
        path=ROOT/name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):findings.append({'path':name,'category':'unsafe_link'});continue
        try:text=publication_text(path)
        except Exception:
            findings.append({'path':name,'category':'unreadable_file'});continue
        for category,pattern in PATTERNS.items():
            if pattern.search(text):findings.append({'path':name,'category':category})
        if re.search(r'(?:C:[/\\]Users[/\\]|/Users/|/home/)[A-Za-z0-9_.-]+',text):findings.append({'path':name,'category':'personal_absolute_path'})
    return findings
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--check',action='store_true');p.add_argument('--write-manifest',action='store_true');p.add_argument('--validate-snapshot',action='store_true');a=p.parse_args()
    paths=candidates();git=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True)
    tracked=git.stdout.decode().split('\0') if git.returncode==0 else []
    if git.returncode:print('SKIP Git history/tracked-file audit: no Git repository; checking proposed publication files')
    findings=audit(sorted(set(paths+[x for x in tracked if x])))
    print(json.dumps({'intended_files':len(paths),'findings':findings},indent=2))
    if findings:raise SystemExit(1)
    if a.write_manifest:(ROOT/'publication_files.json').write_text(json.dumps({'purpose':'Reviewed publication file list; public GitHub publication authorized by user','files':sorted(set(paths+['publication_files.json']))},indent=2)+'\n',encoding='utf-8')
    if a.check and set(json.loads((ROOT/'publication_files.json').read_text())['files'])!=set(paths):raise SystemExit('Publication inventory changed')
    if a.validate_snapshot:
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='publication-check-') as d:
            for name in paths:
                target=Path(d)/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
            env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',RUN_LIVE_OLLAMA_TESTS='0',RUN_LIVE_RETRIEVAL_TESTS='0')
            for command in [['-m','unittest','discover','-s','tests','-v'],['-m','scripts.verify_submission','--offline'],['-m','scripts.verify_submission','--offline','--package','submission'],['-m','scripts.publication_audit','--check']]:subprocess.run([sys.executable,*command],cwd=d,env=env,check=True)
    print('PASS publication path and secret-pattern scan; heuristic checks do not guarantee absence of every secret')
if __name__=='__main__':main()
