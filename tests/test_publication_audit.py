import unittest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
import publication_audit as audit_module
from publication_audit import permitted, PATTERNS

class PublicationAuditTests(unittest.TestCase):
    def test_supported_text_encodings_are_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'text.md'
            for encoding in ['utf-8-sig','utf-16']:
                path.write_bytes('text \u2013 content'.encode(encoding))
                self.assertEqual(audit_module.publication_text(path),'text \u2013 content')
            path.write_bytes(b'\x96')
            with self.assertRaises(UnicodeDecodeError):audit_module.publication_text(path)

    def test_legacy_html_and_documents_are_scanned_and_failures_are_findings(self):
        secret='AIza'+'x'*35
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'provenance').mkdir()
            (root/'artifacts').mkdir()
            html='provenance/legacy.htm'
            (root/html).write_bytes(('<!DOCTYPE HTML><p>\u2013 '+secret+'</p>').encode('cp1252'))
            docx='artifacts/test.docx'
            with zipfile.ZipFile(root/docx,'w') as doc:
                doc.writestr('word/document.xml','<document><t>'+secret[:10]+'</t><t>'+secret[10:]+'</t></document>')
            bad='artifacts/bad.json'
            (root/bad).write_bytes(b'\x96')
            pdf='artifacts/reflection.pdf'
            # A real, minimal text PDF keeps this regression independent of reportlab.
            from pypdf import PdfWriter
            from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject
            writer=PdfWriter()
            page=writer.add_blank_page(612,792)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 10 700 Td ('+secret+') Tj ET').encode('ascii'))
            page[NameObject('/Contents')]=writer._add_object(stream)
            writer.write(root/pdf)
            with patch.object(audit_module,'ROOT',root):
                findings=audit_module.audit([html,docx,pdf,bad])
            for name in [html,docx,pdf]:
                self.assertIn({'path':name,'category':'google_api_key'},findings)
            self.assertIn({'path':bad,'category':'unreadable_file'},findings)
            self.assertNotIn(secret,str(findings))

    def test_local_assets_and_credentials_cannot_be_proposed(self):
        for name in ['.env','submission/.env','submission/index/chroma.sqlite3',
                     'docs/source.pdf','submission/docs/source.pdf','archive/credentials.py',
                     '.venv/Lib/file.py','tmp/output.json','weights.gguf',
                     'artifacts/~$reflection.docx']:
            with self.subTest(name=name):
                self.assertFalse(permitted(name))

    def test_assignment_analysis_and_public_configuration_remain_publishable(self):
        for name in ['.env.example','artifacts/reflection.pdf',
                     'artifacts/final_evaluation.jsonl','docs/source_inventory.json',
                     '.github/workflows/ci.yml']:
            with self.subTest(name=name):
                self.assertTrue(permitted(name))

    def test_secret_patterns_detect_formats_without_real_credentials(self):
        synthetic='AIza' + 'x'*35
        self.assertTrue(PATTERNS['google_api_key'].search(synthetic))
        self.assertFalse(PATTERNS['google_api_key'].search('OLLAMA_BASE_URL=http://127.0.0.1:11434'))
