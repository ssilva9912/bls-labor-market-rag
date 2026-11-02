"""Validate manual source judgments and export fresh page-level evaluation metrics."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'artifacts'
K=4

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def validate(rows,judgments):
    expected={q['id'] for q in load('questions.json')}
    assert len(rows)==len(expected) and {r['id'] for r in rows}==expected
    assert judgments['raw_sha256']==digest(OUT/'final_evaluation.jsonl')
    assert set(judgments['cases'])==expected
    for r in rows:
        j=judgments['cases'][r['id']]
        assert len(j['passages'])==len(r['retrieved_chunks'])<=K
        assert all(p['grade'] in [0,1,2] and p['reason'] for p in j['passages'])
        for arm in ['rag','baseline']:
            assert j[arm+'_correctness'] in ([None] if r[arm+'_error'] else [0,1,2])
            assert j[arm+'_reason']

def retrieval_metrics(row,judgment,reference):
    retrieved={(p['source'],p['page']) for p in row['retrieved_chunks'][:K]}
    gold={(p['filename'],p['pdf_page']) for p in reference['evidence']}
    relevant=sum(p['grade']==2 for p in judgment['passages'][:K])
    return {'k':K,'unit':'PDF page','returned':len(retrieved),'direct_relevant':relevant,
       'precision_at_4':relevant/K,'reference_evidence_recall_at_4':len(retrieved&gold)/len(gold) if gold else None,
       'gold_reference_pages':[{'filename':f,'pdf_page':p} for f,p in sorted(gold)],
       'gold_retrieved':len(retrieved&gold),'gold_denominator':len(gold),
       'evidence_sufficient':judgment['sufficiency']}

def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    rows=[json.loads(x) for x in (OUT/'final_evaluation.jsonl').read_text(encoding='utf-8').splitlines()]
    judgments=load('artifacts/scoring_judgments.json');validate(rows,judgments)
    refs={r['id']:r for r in load('references.json')}
    answerable=[r for r in rows if refs[r['id']]['answerability']=='answerable']
    metrics={r['id']:retrieval_metrics(r,judgments['cases'][r['id']],refs[r['id']]) for r in rows}
    summary={'documents':len(load('docs/source_inventory.json')['documents']),'questions':len(rows),
        'answerable':len(answerable),'k':K,'relevance_unit':'PDF page',
        'recall_label':'Reference-evidence Recall@4, not exhaustive corpus recall',
        'development_set_not_held_out':True,'old_scores_reused':False,
        'paired_completed':sum(not r['rag_error'] and not r['baseline_error'] for r in rows),
        'correctness_exclusions':[],
        'retrieval_exclusions':[r['id'] for r in rows if r not in answerable],
        'retrieval':{'macro_precision_at_4':mean(metrics[r['id']]['precision_at_4'] for r in answerable),
          'macro_reference_evidence_recall_at_4':mean(metrics[r['id']]['reference_evidence_recall_at_4'] for r in answerable),
          'direct_relevant':sum(metrics[r['id']]['direct_relevant'] for r in answerable),'precision_slots':K*len(answerable),
          'actually_returned_pages':sum(metrics[r['id']]['returned'] for r in answerable),
          'canonical_reference_pages_retrieved':sum(metrics[r['id']]['gold_retrieved'] for r in answerable),
          'canonical_reference_pages':sum(metrics[r['id']]['gold_denominator'] for r in answerable),
          'sufficient':sum(metrics[r['id']]['evidence_sufficient'] for r in answerable),'sufficiency_denominator':len(answerable)},
        'mean_retrieval_seconds':mean(r['retrieval_seconds'] for r in rows)}
    for arm in ['rag','baseline']:
        done=[r for r in rows if not r[arm+'_error']]
        a=[r for r in done if r in answerable]
        grades=[judgments['cases'][r['id']][arm+'_correctness'] for r in done]
        summary[arm]={'completed':len(done),'points':sum(grades),'possible_points':2*len(done),'fully_correct':grades.count(2),
            'answerable_points':sum(judgments['cases'][r['id']][arm+'_correctness'] for r in a),
            'answerable_possible_points':2*len(a),'answerable_fully_correct':sum(judgments['cases'][r['id']][arm+'_correctness']==2 for r in a),
            'answerable_completed':len(a),'abstentions':[r['id'] for r in done if judgments['cases'][r['id']][arm+'_abstention']],
            'errors':[{'id':r['id'],'error':r[arm+'_error']} for r in rows if r[arm+'_error']],
            'mean_generation_seconds':mean(r[arm+'_call']['elapsed_seconds'] for r in done) if done else None}
    citations=[j['citation_support'] for j in judgments['cases'].values() if j['citation_support'] is not None]
    summary['citations']={'supported':sum(citations),'eligible_factual_rag_answers':len(citations),'baseline':'N/A; no passages supplied','pure_abstentions':'excluded'}
    summary['abstention_case']={r['id']:{a:judgments['cases'][r['id']][a+'_correctness'] for a in ['rag','baseline']} for r in rows if r not in answerable}
    comparisons=[];passages=[]
    for r in rows:
        j=judgments['cases'][r['id']];m=metrics[r['id']]
        comparisons.append({'id':r['id'],'question':r['question'],'answerability':refs[r['id']]['answerability'],
         'precision_at_4':m['precision_at_4'] if r in answerable else None,'reference_evidence_recall_at_4':m['reference_evidence_recall_at_4'],
         'direct_relevant_pages':m['direct_relevant'],'returned_pages':m['returned'],'gold_reference_pages':json.dumps(m['gold_reference_pages']),
         'gold_retrieved':m['gold_retrieved'],'gold_denominator':m['gold_denominator'],'evidence_sufficient':j['sufficiency'],
         'rag_correctness_0_2':j['rag_correctness'],'baseline_correctness_0_2':j['baseline_correctness'],'citation_support_0_1':j['citation_support'],
         'rag_answer':r['rag_answer'],'baseline_answer':r['baseline_answer'],'rag_reason':j['rag_reason'],'baseline_reason':j['baseline_reason'],
         'citation_reason':j['citation_reason'],'sufficiency_reason':j['sufficiency_reason'],
         'retrieval_seconds':r['retrieval_seconds'],'rag_generation_seconds':(r['rag_call'] or {}).get('elapsed_seconds'),
         'baseline_generation_seconds':(r['baseline_call'] or {}).get('elapsed_seconds'),
         'rag_error':json.dumps(r['rag_error']),'baseline_error':json.dumps(r['baseline_error'])})
        for i,(p,g) in enumerate(zip(r['retrieved_chunks'],j['passages']),1):
            passages.append({'id':r['id'],'rank':i,'filename':p['source'],'pdf_page':p['page'],**g})
    write_csv(OUT/'comparison.csv',comparisons);write_csv(OUT/'retrieval_judgments.csv',passages)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (OUT/'retrieval_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    lines=['# Fresh paired comparison','','K=4; relevance unit=PDF page. Recall is non-exhaustive reference-evidence recall. B9 assessed separately.','','|ID|Precision@4|Reference recall@4|Sufficient|RAG /2|Baseline /2|Citation /1|Assessment|','|---|---|---|---|---|---|---|---|']
    for r in comparisons:
        lines.append('|'+ '|'.join(str(r[k]) for k in ['id','precision_at_4','reference_evidence_recall_at_4','evidence_sufficient','rag_correctness_0_2','baseline_correctness_0_2','citation_support_0_1','rag_reason'])+'|')
    lines+=['',f"Macro over eight answerable cases: Precision@4={summary['retrieval']['macro_precision_at_4']:.3f}; reference-evidence Recall@4={summary['retrieval']['macro_reference_evidence_recall_at_4']:.3f}."]
    (OUT/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
