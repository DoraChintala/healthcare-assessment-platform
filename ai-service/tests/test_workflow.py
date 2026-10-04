from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from app.workflow import build_graph
from app.catalog import load
from app.models import Candidate
from app.provider import grounded, mock_extract
from app.rules import evaluate
import pytest

def initial(text):
    return {'tenant':'demo-hospital','resume_text':text,'job_id':'rn-icu'}

def test_pass_uses_simulated_evidence(tmp_path):
    with SqliteSaver.from_conn_string(str(tmp_path/'graph.db')) as saver:
        graph=build_graph(saver)
        result=graph.invoke(initial(load('candidates.json')[0]['resume_text']),{'configurable':{'thread_id':'pass'}})
        assert result['summary']['recommendation']=='REQUIREMENTS_MET'
        assert result['registry_evidence']['source']=='SIMULATED_REGISTRY'
        assert result['candidate']['evidence']['license_number']['source_id']=='resume'
        assert result['needs_clarification'] is False

def test_checkpoint_survives_restart_and_review(tmp_path):
    path=str(tmp_path/'graph.db'); cfg={'configurable':{'thread_id':'missing'}}
    with SqliteSaver.from_conn_string(path) as saver:
        graph=build_graph(saver)
        result=graph.invoke(initial(load('candidates.json')[1]['resume_text']),cfg)
        assert result['__interrupt__']
        assert graph.get_state(cfg).values['needs_clarification']
    with SqliteSaver.from_conn_string(path) as saver:
        graph=build_graph(saver)
        result=graph.invoke(Command(resume={'notes':'Confirmed synthetic document','corrections':{'license_number':'DEMO-VA-1001'},'resume_id':'review-1'}),cfg)
        assert result['summary']['recommendation']=='REQUIREMENTS_MET'
        assert result['candidate']['evidence']['license_number']['source_id']=='reviewer'
        assert not graph.get_state(cfg).next

def test_injection_cannot_change_expired_license():
    c,_=mock_extract(load('candidates.json')[4]['resume_text'])
    rules,_=evaluate(c,{'minimum_years':3,'license_state':'VA'})
    assert next(r for r in rules if r['id']=='license')['status']=='FAIL'

def test_equivalent_qualifications_ignore_names():
    a=load('candidates.json')[0]['resume_text']
    b=a.replace('Synthetic Candidate A','Different Name')
    c1,_=mock_extract(a);c2,_=mock_extract(b)
    assert c1==c2

def test_unsupported_extraction_is_rejected():
    c=Candidate(years_experience=25,evidence={'years_experience':{'source_id':'resume','quote':'Experience: 5 years'}})
    with pytest.raises(ValueError):
        grounded(c,{'resume':'Experience: 5 years'})
