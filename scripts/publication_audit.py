"""Audit files Git would publish for excluded paths and secret patterns.

Checks tracked files plus untracked files that .gitignore does not exclude.
Matches are reported by path and category only; secret text is never printed.
The scan is a heuristic and cannot guarantee that no secret exists.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_PARTS = {'archive', 'tmp', 'index', 'results', '__pycache__', '.git', '.uv-cache', '.cache',
                  '.ollama', 'models', 'outputs', 'checkpoints', 'wandb'}
EXCLUDED_SUFFIXES = {'.key', '.pem', '.gguf', '.safetensors', '.bin', '.pt', '.sqlite3', '.db', '.pyc', '.zip'}


def permitted(name: str) -> bool:
    p = Path(name)
    if p.name.startswith('~$'):
        return False
    if any(part in EXCLUDED_PARTS or part.startswith('.venv') for part in p.parts):
        return False
    if p.name.startswith('.env') and p.name != '.env.example':
        return False
    if 'credential' in p.name.lower() or 'service-account' in p.name.lower():
        return False
    if p.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if p.suffix.lower() == '.pdf':
        # Only the registered BLS corpus and the experiment reflections are publishable PDFs.
        if p.parent.as_posix() == 'corpus/pdfs':
            inventory = ROOT / 'corpus' / 'source_inventory.json'
            return p.name in {r['filename'] for r in json.loads(inventory.read_text())['documents']}
        return p.name == 'reflection.pdf' and p.parts[0] == 'experiments'
    return True


PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'google_api_key': re.compile(r'AIza[0-9A-Za-z_-]{35}'),
    'github_token': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'openai_key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}'),
    'huggingface_token': re.compile(r'\bhf_[A-Za-z0-9]{30,}'),
    'literal_secret_assignment': re.compile(
        r'''(?im)^\s*(?:[A-Z_]*(?:API_KEY|ACCESS_TOKEN|CLIENT_SECRET|PASSWORD|HF_TOKEN))\s*=\s*["']?[A-Za-z0-9_+/=-]{20,}'''),
}


def publication_text(path: Path) -> str:
    """Use strict decoders and document readers; never discard bytes."""
    import xml.etree.ElementTree as ET
    import zipfile
    data = path.read_bytes()
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise ValueError('Encrypted PDF')
        return '\n'.join(page.extract_text() for page in reader.pages)
    if path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as doc:
            if 'word/document.xml' not in doc.namelist():
                raise ValueError('Invalid DOCX')
            parts = []
            for name in doc.namelist():
                if name.endswith(('.xml', '.rels')):
                    raw = doc.read(name).decode('utf-8-sig')
                    parts.extend([raw, ''.join(ET.fromstring(raw).itertext())])
            return '\n'.join(parts)
    if path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        return ''
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        # Legacy BLS HTML uses Windows-1252 punctuation; anything else fails closed.
        if path.suffix.lower() not in {'.htm', '.html'}:
            raise
        text = data.decode('cp1252')
        if not re.match(r'\s*<!doctype html', text, re.I):
            raise ValueError('Invalid HTML')
        return text


def audit(paths):
    findings = []
    for name in paths:
        if not permitted(name):
            findings.append({'path': name, 'category': 'excluded_path'})
            continue
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            findings.append({'path': name, 'category': 'unsafe_link'})
            continue
        try:
            text = publication_text(path)
        except Exception:
            findings.append({'path': name, 'category': 'unreadable_file'})
            continue
        for category, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({'path': name, 'category': category})
        if re.search(r'(?:C:[/\\]Users[/\\]|/Users/|/home/)[A-Za-z0-9_.-]+', text):
            findings.append({'path': name, 'category': 'personal_absolute_path'})
    return findings


def candidates() -> list[str]:
    git = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                         cwd=ROOT, capture_output=True, check=True)
    return sorted({x for x in git.stdout.decode().split('\0') if x and (ROOT / x).is_file()})


def main() -> None:
    paths = candidates()
    findings = audit(paths)
    print(json.dumps({'files': len(paths), 'findings': findings}, indent=2))
    if findings:
        sys.exit(1)
    print('PASS publication path and secret-pattern scan (heuristic)')


if __name__ == '__main__':
    main()
