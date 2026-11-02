"""Approved BLS corpus: acquisition and offline integrity checks, with no model calls."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent
POLICY='https://www.bls.gov/opub/copyright-information.htm'
SOURCES=[
 ('D1','01_bls_state_unemployment_annual_2024.pdf','Regional and State Unemployment - 2024 Annual Averages','2024 annual','2025-03-05','srgune_03052025'),
 ('D2','02_bls_state_employment_unemployment_dec2024.pdf','State Employment and Unemployment - December 2024','December 2024 monthly','2025-01-28','laus_01282025'),
 ('D3','03_bls_occupational_employment_wages_may2024.pdf','Occupational Employment and Wages - May 2024','May 2024','2025-04-02','ocwage_04022025'),
 ('D4','04_bls_business_employment_dynamics_q42024.pdf','Business Employment Dynamics - Fourth Quarter 2024','Q4 2024','2025-07-30','cewbd_07302025'),
 ('D5','05_bls_employment_projections_2024_2034.pdf','Employment Projections - 2024-2034','U.S. 2024-2034','2025-08-28','ecopro_08282025'),
 ('D6','06_bls_metro_employment_unemployment_dec2024.pdf','Metropolitan Area Employment and Unemployment - December 2024','December 2024 metro','2025-02-05','metro_02052025'),
 ('D7','07_bls_employment_situation_dec2024.pdf','The Employment Situation - December 2024','December 2024 national','2025-01-10','empsit_01102025'),
 ('D8','08_bls_job_openings_turnover_dec2024.pdf','Job Openings and Labor Turnover - December 2024','December 2024 national','2025-02-04','jolts_02042025')]

def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def download():
    docs=ROOT/'docs'; docs.mkdir(exist_ok=True)
    raw=ROOT/'provenance/sources';raw.mkdir(parents=True,exist_ok=True)
    prior={x['filename']:x for x in json.loads((docs/'source_inventory.json').read_text(encoding='utf-8')).get('documents',[])} if (docs/'source_inventory.json').exists() else {}
    records=[]
    for ident,filename,title,period,date,stem in SOURCES:
        pdf=docs/filename; html=raw/(stem+'.htm')
        base='https://www.bls.gov/news.release/archives/'+stem
        for target,url in [(pdf,base+'.pdf'),(html,base+'.htm')]:
            if target.exists():continue
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/pdf,text/html;q=0.9,*/*;q=0.8'}),timeout=30) as response:
                body=response.read()
            if target.suffix=='.pdf' and not body.startswith(b'%PDF'):
                raise RuntimeError('Official PDF unavailable; stop for verified labelled HTML-to-PDF conversion: '+filename)
            target.write_bytes(body)
        record={'id':ident,'filename':filename,'title':title,'period':period,'release_date':date,
            'retrieved_utc':prior.get(filename,{}).get('retrieved_utc',datetime.now(timezone.utc).isoformat()),
            'source_url':base+'.htm','pdf_url':base+'.pdf','sha256':sha256(pdf),
            'format':'official_pdf_unmodified','generated_snapshot':False,'pdf_pages':len(PdfReader(pdf).pages),
            'html_snapshot':html.relative_to(ROOT).as_posix(),'html_sha256':sha256(html),
            'reuse_terms_url':POLICY,'reuse_basis':'BLS public-domain text and statistical data; attribution requested; previously copyrighted photos/illustrations excluded; emblem is separately protected and not project branding.',
            'attribution':'Source: U.S. Bureau of Labor Statistics (BLS).'}
        records.append(record)
        print(ident,filename,record['pdf_pages'],'official PDF pages',flush=True)
    (docs/'source_inventory.json').write_text(json.dumps({'documents':records,'exact_document_count':8,
        'requirement_change':'Latest user instruction superseded five documents: at least eight documents and eight questions; eight PDFs and nine questions selected.',
        'ingestion_source':'Saved PDFs only; HTML used solely to cross-check source fidelity.',
        'terms_verified_before_download':True},indent=2)+'\n',encoding='utf-8')
    review={'source_url':POLICY,'reviewed_utc':datetime.now(timezone.utc).isoformat(),
        'retrieval_method':'Official BLS policy read through web browsing; direct Python policy GET returned 403. This is a review record, not an HTML copy.',
        'supporting_excerpt':'You are free to use our public domain material without specific permission',
        'conditions':'BLS requests attribution; previously copyrighted photographs/illustrations excluded; BLS emblem separately restricted.',
        'corpus_assessment':'Original BLS statistical releases and BLS-created tables/charts; no credited third-party photographs/illustrations selected. No endorsement or project use of emblem.'}
    (ROOT/'provenance/reuse_terms.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
    print('Verified',verify(),'official PDFs; no generated corpus snapshots needed.')

def verify():
    inv=json.loads((ROOT/'docs/source_inventory.json').read_text(encoding='utf-8'))
    records=inv['documents']; names={p.name for p in (ROOT/'docs').glob('*.pdf')}
    if len(records)!=8 or len(names)!=8 or names!={r['filename'] for r in records}:
        raise ValueError('Corpus must contain exactly eight registered PDFs')
    for r in records:
        if sha256(ROOT/'docs'/r['filename'])!=r['sha256']:
            raise ValueError('PDF hash mismatch: '+r['filename'])
        if r['reuse_terms_url']!=POLICY or not r['release_date'] or not r['retrieved_utc']:
            raise ValueError('Missing source/reuse provenance')
        if sha256(ROOT/r['html_snapshot'])!=r['html_sha256']:
            raise ValueError('HTML provenance hash mismatch')
    return len(records)

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('command',choices=['download','verify']);args=parser.parse_args()
    download() if args.command=='download' else print('Verified',verify(),'PDFs and provenance offline.')
