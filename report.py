"""Build the editable one-page reflection from the fresh scored results (OOXML, no model calls)."""
import json
import argparse
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'artifacts'

def build():
    s=json.loads((OUT/'summary.json').read_text());r=s['retrieval']
    content=json.loads((OUT/'analysis_content.json').read_text(encoding='utf-8'))
    title=content['title']
    paragraphs=content['paragraphs']
    table=[['Measure','RAG','No retrieval'],
      ['Correctness points',f'{s["rag"]["points"]}/{s["rag"]["possible_points"]}',f'{s["baseline"]["points"]}/{s["baseline"]["possible_points"]}'],
      ['Fully correct responses',f'{s["rag"]["fully_correct"]}/9',f'{s["baseline"]["fully_correct"]}/9'],
      ['Answerable cases only',f'{s["rag"]["answerable_points"]}/16 points',f'{s["baseline"]["answerable_points"]}/16 points'],
      ['Supported factual citations',f'{s["citations"]["supported"]}/{s["citations"]["eligible_factual_rag_answers"]}','Not applicable']]
    def p(text,style=None):
        props=f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
        return f'<w:p>{props}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
    def tbl(rows):
        xml='<w:tbl><w:tblPr><w:tblW w:w="10100" w:type="dxa"/><w:tblBorders><w:bottom w:val="single" w:sz="4" w:color="BBBBBB"/></w:tblBorders><w:tblCellMar><w:top w:w="55" w:type="dxa"/><w:bottom w:w="55" w:type="dxa"/><w:left w:w="85" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid><w:gridCol w:w="4900"/><w:gridCol w:w="2600"/><w:gridCol w:w="2600"/></w:tblGrid>'
        for i,row in enumerate(rows):
            xml+='<w:tr>'
            for j,value in enumerate(row):
                shade='<w:shd w:fill="EEEEEE"/>' if i==0 else ''
                xml+=f'<w:tc><w:tcPr><w:tcW w:w="{4900 if j==0 else 2600}" w:type="dxa"/>{shade}</w:tcPr>'+p(value,'TableText')+'</w:tc>'
            xml+='</w:tr>'
        return xml+'</w:tbl>'
    body=p(title,'Title')
    for i,(heading,text) in enumerate(paragraphs):
        body+=p(heading,'Heading1')+p(text)
        # Detailed tables are retained in comparison.csv and comparison.md.
    body+='<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="800" w:right="1000" w:bottom="800" w:left="1000" w:header="0" w:footer="0"/></w:sectPr>'
    document='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+body+'</w:body></w:document>'
    styles='''<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="85" w:line="248" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="000000"/><w:sz w:val="21"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="150"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="000000"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="65" w:after="45"/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="TableText"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0"/></w:pPr><w:rPr><w:sz w:val="20"/></w:rPr></w:style></w:styles>'''
    types='''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'''
    rels='''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    docrels='''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    with ZipFile(OUT/'reflection.docx','w',ZIP_DEFLATED) as archive:
        for name,content in {'[Content_Types].xml':types,'_rels/.rels':rels,'word/document.xml':document,'word/styles.xml':styles,'word/_rels/document.xml.rels':docrels}.items():archive.writestr(name,content)
    (OUT/'reflection.md').write_text('# '+title+'\n\n'+'\n\n'.join('## '+h+'\n\n'+t for h,t in paragraphs)+'\n',encoding='utf-8')
    (OUT/'quality_assessment.md').write_text('# Quality assessment\n\n'+'\n\n'.join(t for _,t in paragraphs)+f'\n\nCitation support excludes the two pure RAG abstentions (B1/B9), leaving seven factual responses. Answer correctness includes all nine completed cases; answerable-only denominators are eight questions / sixteen points. The B3 contradictory partial abstention is retained and receives zero under the frozen core-contradiction rule. No transport failures were treated as wrong answers.\n',encoding='utf-8')
    print('Created editable reflection.docx from fresh results; export in Word and verify one page.')
def pdf():
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from pypdf import PdfReader
    from xml.etree import ElementTree as ET
    with ZipFile(OUT/'reflection.docx') as archive:
        doc=ET.fromstring(archive.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='BodyReport',fontName='Helvetica',fontSize=10,leading=12.5,spaceAfter=6))
    story=[]
    for node in doc.find('w:body',ns):
        if node.tag.endswith('}p'):
            text=''.join(node.itertext())
            style=node.find('w:pPr/w:pStyle',ns)
            value=style.get('{'+ns['w']+'}val') if style is not None else None
            story.append(Paragraph(escape(text),styles['Title'] if value=='Title' else styles['Heading3'] if value=='Heading1' else styles['BodyReport']))
        elif node.tag.endswith('}tbl'):
            rows=[[''.join(cell.itertext()) for cell in row.findall('w:tc',ns)] for row in node.findall('w:tr',ns)]
            table=Table(rows,colWidths=[245,125,125]);table.setStyle(TableStyle([('FONTSIZE',(0,0),(-1,-1),9.5),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),('BOTTOMPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5)]));story.extend([table,Spacer(1,6)])
    target=OUT/'reflection.pdf';SimpleDocTemplate(str(target),pagesize=letter,leftMargin=48,rightMargin=48,topMargin=30,bottomMargin=30).build(story)
    if len(PdfReader(target).pages)!=1:raise ValueError('Reflection PDF must fit one page')
    (OUT/'document_validation.json').write_text(json.dumps({'docx':'reflection.docx','docx_structure':'OOXML parsed successfully; editable Word paragraphs and table, no macros or external relationships.',
       'native_word_render':'Not performed by this generator; native DOCX pagination requires a separate renderer.',
       'pdf':'reflection.pdf','pdf_pages':1,'pdf_renderer':'ReportLab from the actual DOCX content; this is not a native Word layout render.',
       'limitation':'DOCX designed for one page with fixed Letter size, margins, font and spacing; native Word pagination was not verified and can vary.'},indent=2),encoding='utf-8')
    print('Verified one-page PDF generated from DOCX content; native Word pagination remains unverified.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--pdf-only',action='store_true');args=parser.parse_args()
    pdf() if args.pdf_only else build()
