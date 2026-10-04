import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'data'
def load(name):
    return json.loads((ROOT / name).read_text())
JOBS = {job['id']: job for job in load('jobs.json')}
POLICIES = load('policies.json')
REGISTRY = load('registry.json')

def job_for(tenant, job_id):
    # The starter exposes a single demo tenant. Other records are isolation test fixtures.
    if tenant != 'demo-hospital' or job_id not in JOBS:
        raise LookupError('Job not found for tenant')
    return JOBS[job_id]
