import json
import httpx
import pytest
from app import config
from app.provider import extract

def configure(monkeypatch,payload):
    original=httpx.Client
    def respond(request):
        body=json.loads(request.content)
        assert body['messages'][0]['role']=='system'
        assert 'tools' not in body
        return httpx.Response(200,json=payload)
    monkeypatch.setattr(config,'LLM_MODE','compatible')
    monkeypatch.setattr('app.provider.httpx.Client',lambda **kwargs:original(transport=httpx.MockTransport(respond)))

def test_compatible_endpoint_grounds_values_and_usage(monkeypatch):
    configure(monkeypatch,{'choices':[{'message':{'content':json.dumps({'years_experience':5,'license_number':None,'license_state':None,'evidence':{'years_experience':{'source_id':'resume','quote':'Experience: 5 years'}}})}}],'usage':{'prompt_tokens':100,'completion_tokens':20}})
    candidate,usage=extract('Experience: 5 years')
    assert candidate.years_experience==5
    assert usage['input_tokens']==100 and usage['output_tokens']==20

def test_compatible_endpoint_cannot_claim_unsupported_experience(monkeypatch):
    configure(monkeypatch,{'choices':[{'message':{'content':json.dumps({'years_experience':40,'evidence':{'years_experience':{'source_id':'resume','quote':'Experience: 5 years'}}})}}]})
    with pytest.raises(ValueError):extract('Experience: 5 years')
