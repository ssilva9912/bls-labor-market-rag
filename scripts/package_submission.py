"""Build and verify a deterministic release ZIP; never modify submission/."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED
from scripts.publication_audit import ROOT, audit, candidates
from scripts.verify_submission import verify_package


def build():
    names = [name for name in candidates() if not name.startswith('submission/')]
    findings = audit(names)
    if findings:
        raise ValueError(f'Publication audit failed: {findings}')
    output = ROOT / 'tmp' / 'bls-labor-market-rag-submission.zip'
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        for name in names:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        (stage / 'publication_files.json').write_text(json.dumps({
            'purpose': 'Standalone release assignment', 'files': sorted(names)
        }, indent=2) + '\n', encoding='utf-8')
        hashes = {name: hashlib.sha256((stage / name).read_bytes()).hexdigest()
                  for name in sorted(names)}
        (stage / 'submission_checksums.json').write_text(
            json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
        verify_package(stage)
        with ZipFile(output, 'w', compression=ZIP_STORED) as archive:
            for name in sorted([*names, 'submission_checksums.json']):
                entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, (stage / name).read_bytes())
        with ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP integrity failure')
            for name, digest in hashes.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise ValueError('ZIP content mismatch: ' + name)
    print(output)
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print('Verified complete assignment; submission/ was not modified.')
    return output


if __name__ == '__main__':
    build()
