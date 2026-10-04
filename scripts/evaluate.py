"""Exact-value extraction baseline. Run from ai-service with PYTHONPATH=."""
import json
from app.provider import extract
from app.catalog import load,JOBS
from app.rules import evaluate,summary_for
from app.retrieval import retrieve

labels=[
 {'years_experience':5,'license_number':'DEMO-VA-1001','license_state':'VA','recommendation':'REQUIREMENTS_MET'},
 {'years_experience':5,'license_number':None,'license_state':'VA','recommendation':'VERIFICATION_PENDING'},
 {'years_experience':4,'license_number':'DEMO-VA-1002','license_state':'VA','recommendation':'REQUIREMENTS_NOT_MET'},
 {'years_experience':1,'license_number':'DEMO-VA-1001','license_state':'VA','recommendation':'REQUIREMENTS_NOT_MET'},
 {'years_experience':5,'license_number':'DEMO-VA-1002','license_state':'VA','recommendation':'REQUIREMENTS_NOT_MET'},
]
tp=fp=fn=correct=0
for example,label in zip(load('candidates.json'),labels):
    candidate,_=extract(example['resume_text'])
    for field in ('years_experience','license_number','license_state'):
        predicted,expected=getattr(candidate,field),label[field]
        if predicted is not None and predicted==expected: tp+=1
        elif predicted!=expected:
            fp+=int(predicted is not None);fn+=int(expected is not None)
    rules,_=evaluate(candidate,JOBS[example['job_id']])
    policies=retrieve('demo-hospital',JOBS[example['job_id']],'license assessment')
    correct+=summary_for(rules,policies).recommendation==label['recommendation']
precision=tp/(tp+fp) if tp+fp else 0
recall=tp/(tp+fn) if tp+fn else 0
f1=2*precision*recall/(precision+recall) if precision+recall else 0
print(json.dumps({'examples':len(labels),'exact_value_precision':precision,'exact_value_recall':recall,'exact_value_f1':f1,'recommendation_accuracy':correct/len(labels),'note':'Small synthetic smoke dataset. Mock-mode scores validate parsing, not real model quality.'},indent=2))
