import json
import time
from langgraph.checkpoint.sqlite import SqliteSaver
from app import store
from app.catalog import load
from app.workflow import build_graph
from app.worker import process_one

def submit(client,headers,index=0,key='unique-1'):
    sample=load('candidates.json')[index]
    return client.post('/assessments',json={'resume_text':sample['resume_text'],'job_id':sample['job_id']},headers={**headers,'Idempotency-Key':key})

def test_idempotency_and_conflict(client,headers):
    a=submit(client,headers);b=submit(client,headers)
    assert a.status_code==202 and a.json()['id']==b.json()['id']
    assert submit(client,headers,index=1).status_code==409

def test_tenant_and_role_boundaries(client,headers,tmp_path):
    row=submit(client,headers).json()
    assert client.get('/assessments/'+row['id'],headers={**headers,'X-Tenant-ID':'other-hospital'}).status_code==404
    assert client.get('/assessments').status_code==401
    with SqliteSaver.from_conn_string(str(tmp_path/'graph.db')) as saver:
        process_one(build_graph(saver))
    row=client.get('/assessments/'+row['id'],headers=headers).json()
    response=client.post('/assessments/'+row['id']+'/review',headers={**headers,'X-Role':'viewer'},json={'action':'approve','notes':'Looks good','expected_version':row['version']})
    assert response.status_code==403

def test_end_to_end_clarification_and_approval(client,headers,tmp_path):
    row=submit(client,headers,index=1).json(); assessment_id=row['id']
    path=str(tmp_path/'graph.db')
    with SqliteSaver.from_conn_string(path) as saver:
        assert process_one(build_graph(saver))
    row=client.get('/assessments/'+assessment_id,headers=headers).json()
    assert row['status']=='AWAITING_CLARIFICATION'
    response=client.post('/assessments/'+assessment_id+'/review',headers=headers,json={'action':'clarify','notes':'Checked demo evidence','corrections':{'license_number':'DEMO-VA-1001'},'expected_version':row['version']})
    assert response.status_code==200
    with SqliteSaver.from_conn_string(path) as saver:
        assert process_one(build_graph(saver))
    row=client.get('/assessments/'+assessment_id,headers=headers).json()
    assert row['status']=='AWAITING_APPROVAL'
    decision={'action':'approve','notes':'Reviewed simulated evidence','expected_version':row['version']}
    response=client.post('/assessments/'+assessment_id+'/review',headers=headers,json=decision)
    assert response.json()['status']=='COMPLETED'
    assert client.post('/assessments/'+assessment_id+'/review',headers=headers,json=decision).status_code==409
    actions=[r['action'] for r in client.get('/assessments/'+assessment_id+'/audit',headers=headers).json()]
    assert 'REVIEW_CLARIFY' in actions and 'REVIEW_APPROVE' in actions

def test_expired_license_is_not_silently_approved(client,headers,tmp_path):
    row=submit(client,headers,index=2).json()
    with SqliteSaver.from_conn_string(str(tmp_path/'graph.db')) as saver:
        process_one(build_graph(saver))
    row=client.get('/assessments/'+row['id'],headers=headers).json()
    assert row['status']=='AWAITING_APPROVAL'
    assert row['result']['summary']['recommendation']=='REQUIREMENTS_NOT_MET'

def test_crashed_worker_lease_is_reclaimed(client,headers,tmp_path):
    row=submit(client,headers).json()
    abandoned=store.claim()
    with store.Session() as db:
        record=db.get(store.Assessment,row['id']);record.lease_until=time.time()-1;db.commit()
    with SqliteSaver.from_conn_string(str(tmp_path/'graph.db')) as saver:
        process_one(build_graph(saver))
    assert store.get('demo-hospital',row['id'])['status']=='AWAITING_APPROVAL'
    # Stale owners cannot replace results after ownership changes.
    store.finish(abandoned,{},'old worker error')
    assert store.get('demo-hospital',row['id'])['status']=='AWAITING_APPROVAL'

def test_unknown_request_properties_are_rejected(client,headers):
    sample=load('candidates.json')[0]
    response=client.post('/assessments',headers={**headers,'Idempotency-Key':'x'},json={'resume_text':sample['resume_text'],'tenant':'other-hospital'})
    assert response.status_code==422
