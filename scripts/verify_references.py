"""Verify supporting excerpts in original PDF text and export the reference table."""
import csv
import json
import re
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def normalized(text):
    return re.sub(r'[^\w$%.]+', '', text.lower()).replace('_', '')


def main():
    refs = json.loads((ROOT / 'references.json').read_text(encoding='utf-8'))
    questions = {q['id']: q for q in json.loads((ROOT / 'questions.json').read_text(encoding='utf-8'))}
    readers = {}
    rows = []
    for ref in refs:
        for evidence in ref['evidence']:
            name, number = evidence['filename'], evidence['pdf_page']
            reader = readers.setdefault(name, PdfReader(ROOT / 'docs' / name))
            source = normalized(reader.pages[number - 1].extract_text())
            cursor = 0
            for line in evidence['supporting_excerpt'].splitlines():
                needle = normalized(line)
                pos = source.find(needle, cursor)
                if pos < 0:
                    raise RuntimeError(f'Excerpt mismatch: {ref["id"]}, {name}, PDF p.{number}')
                cursor = pos + len(needle)
        rows.append({'id': ref['id'], 'question': ref['question'],
            'original_question': questions[ref['id']]['original_question'],
            'explicit_correction': questions[ref['id']]['correction'] or '',
            'answerability': ref['answerability'], 'reference_answer': ref['reference_answer'],
            'filename': '; '.join(e['filename'] for e in ref['evidence']),
            'pdf_page': '; '.join(str(e['pdf_page']) for e in ref['evidence']),
            'supporting_excerpt': '\n\n'.join(f"{e['filename']} PDF p.{e['pdf_page']}: {e['supporting_excerpt']}" for e in ref['evidence']),
            'required_criteria': '\n'.join(ref['required_criteria']), 'ambiguity': ref['ambiguity']})
    out = ROOT / 'artifacts'
    out.mkdir(exist_ok=True)
    with (out / 'source_reference_table.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    blocks = ['# Source and reference table', '', 'Fresh eight-document corpus. Physical PDF pages are one-based. Original questions remain in provenance; B9 is intentionally unanswerable from this corpus.', '']
    for row in rows:
        blocks.extend([f"## {row['id']} — {row['answerability']}", '', row['question'], '',
                       '**Reference:** ' + row['reference_answer'], '',
                       '**Evidence:** ' + row['supporting_excerpt'], '',
                       '**Ambiguity:** ' + row['ambiguity'], ''])
        if row['explicit_correction']:
            blocks.extend(['**Correction:** ' + row['explicit_correction'], ''])
    (out / 'source_reference_table.md').write_text('\n'.join(blocks), encoding='utf-8')
    print(f'Verified PDF excerpts for {len(refs)} references; original questions preserved separately.')


if __name__ == '__main__':
    main()
