import hmac
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from . import config, store
from .catalog import JOBS, job_for, load
from .models import AssessmentRequest, ReviewRequest, Candidate

@asynccontextmanager
async def lifespan(app):
    store.init_db()
    yield

app = FastAPI(title='Healthcare Assessment AI Service', version='0.1.0', lifespan=lifespan)

# CORS — allow the gateway origin (and optionally direct browser access in dev)
_allowed = [o.strip() for o in config.CORS_ORIGINS.split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed or ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

def identity(x_service_token: str = Header(''), x_tenant_id: str = Header(''), x_actor_id: str = Header(''), x_role: str = Header('')):
    if not hmac.compare_digest(x_service_token,config.SERVICE_TOKEN):
        raise HTTPException(401,'Internal authentication required')
    if not re.fullmatch(r'[A-Za-z0-9-]{1,100}',x_tenant_id) or not re.fullmatch(r'[A-Za-z0-9@._-]{1,100}',x_actor_id):
        raise HTTPException(400,'Invalid identity context')
    if x_role not in ('viewer','reviewer'):
        raise HTTPException(403,'Unsupported role')
    return {'tenant':x_tenant_id,'actor':x_actor_id,'role':x_role}

@app.get('/health')
def health():
    return {'status':'ok','llm_mode':config.LLM_MODE,'retrieval_mode':config.RETRIEVAL_MODE,'registry_mode':'SIMULATED'}

@app.get('/metrics',dependencies=[Depends(identity)])
def metrics():
    return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

@app.get('/jobs')
def jobs(who=Depends(identity)):
    return list(JOBS.values()) if who['tenant']=='demo-hospital' else []

@app.get('/samples')
def samples(who=Depends(identity)):
    return load('candidates.json') if who['tenant']=='demo-hospital' else []

@app.get('/assessments')
def assessments(who=Depends(identity)):
    return store.list_assessments(who['tenant'])

@app.post('/assessments',status_code=202)
def create_assessment(body: AssessmentRequest,idempotency_key: str=Header(...),who=Depends(identity)):
    if not re.fullmatch(r'[A-Za-z0-9-]{1,100}',idempotency_key):
        raise HTTPException(400,'Invalid idempotency key')
    try:
        job_for(who['tenant'],body.job_id)
        return store.create(who['tenant'],idempotency_key,body.model_dump(),who['actor'])
    except LookupError:
        raise HTTPException(404,'Job not found')
    except ValueError as exc:
        raise HTTPException(409,str(exc))

@app.get('/assessments/{assessment_id}')
def get_assessment(assessment_id: str,who=Depends(identity)):
    result = store.get(who['tenant'],assessment_id)
    if not result:
        raise HTTPException(404,'Assessment not found')
    return result

@app.get('/assessments/{assessment_id}/audit')
def get_audit(assessment_id: str,who=Depends(identity)):
    get_assessment(assessment_id,who)
    return store.audit(who['tenant'],assessment_id)

@app.post('/assessments/{assessment_id}/review')
def review_assessment(assessment_id: str,body: ReviewRequest,who=Depends(identity)):
    if who['role']!='reviewer':
        raise HTTPException(403,'Reviewer role required')
    try:
        # Validate corrections before queuing a resume command.
        Candidate.model_validate(body.corrections)
        return store.review(who['tenant'],assessment_id,who['actor'],body.model_dump())
    except LookupError:
        raise HTTPException(404,'Assessment not found')
    except ValueError as exc:
        raise HTTPException(409,str(exc))
