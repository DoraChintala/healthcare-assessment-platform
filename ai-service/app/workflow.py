from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from .models import Candidate
from .provider import extract, grounded
from .catalog import job_for
from .retrieval import retrieve
from .rules import evaluate, summary_for, RULES_VERSION
from .metrics import measured

class State(TypedDict, total=False):
    tenant: str
    resume_text: str
    job_id: str
    candidate: dict
    policies: list
    rules: list
    registry_evidence: dict | None
    summary: dict
    needs_clarification: bool
    extraction_error: str | None
    rules_version: str
    usage: dict
    applied_resume_id: str
    reviewer_source: str
    review_round: int

def extraction_node(state):
    try:
        candidate, usage = extract(state['resume_text'])
        return {'candidate':candidate.model_dump(), 'usage':usage, 'extraction_error':None}
    except ValueError:
        # Invalid model output is never converted into positive eligibility.
        return {'candidate':Candidate().model_dump(),'usage':{},'extraction_error':'Extraction output could not be grounded; reviewer correction required'}

def retrieval_node(state):
    job = job_for(state['tenant'], state['job_id'])
    policies = retrieve(state['tenant'], job, job['title'] + ' license experience assessment')
    if not set(job['policy_ids']).issubset({p['id'] for p in policies}):
        raise ValueError('Required policy evidence unavailable')
    return {'policies':policies}

def evaluation_node(state):
    candidate = Candidate.model_validate(state['candidate'])
    grounded(candidate, {'resume':state['resume_text'],'reviewer':state.get('reviewer_source','')})
    rules, registry = evaluate(candidate, job_for(state['tenant'], state['job_id']))
    return {'rules':rules,'registry_evidence':registry,'rules_version':RULES_VERSION}

def summary_node(state):
    summary = summary_for(state['rules'], state['policies'])
    return {'summary':summary.model_dump(),'needs_clarification':any(r['status']=='UNKNOWN' for r in state['rules'])}

def clarification_node(state):
    # No writes before interrupt: this node is replayed when resumed.
    reply = interrupt({'reason':'Missing or conflicting evidence','rules':state['rules'],
                       'fields':['years_experience','license_number','license_state']})
    candidate = dict(state['candidate'])
    evidence = dict(candidate['evidence'])
    source = state.get('reviewer_source','') + '\n' + reply['notes']
    for field, value in reply['corrections'].items():
        if field not in {'years_experience','license_number','license_state'}:
            raise ValueError('Unsupported correction field')
        if field != 'years_experience':
            value = str(value).upper()
        quote = f'{field}={value}'
        source += '\n' + quote
        candidate[field] = value
        evidence[field] = {'source_id':'reviewer','quote':quote}
    candidate['evidence'] = evidence
    candidate = grounded(Candidate.model_validate(candidate), {'resume':state['resume_text'],'reviewer':source})
    return {'candidate':candidate.model_dump(),'reviewer_source':source,'applied_resume_id':reply['resume_id'],
            'review_round':state.get('review_round',0)+1,'extraction_error':None}

def build_graph(checkpointer):
    graph = StateGraph(State)
    for name, node in [('extract',extraction_node),('retrieve',retrieval_node),('evaluate',evaluation_node),('summarize',summary_node),('clarify',clarification_node)]:
        graph.add_node(name,measured(name,node))
    graph.add_edge(START,'extract')
    graph.add_edge('extract','retrieve')
    graph.add_edge('retrieve','evaluate')
    graph.add_edge('evaluate','summarize')
    graph.add_conditional_edges('summarize', lambda s: 'clarify' if s['needs_clarification'] else END)
    graph.add_edge('clarify','evaluate')
    return graph.compile(checkpointer=checkpointer)
