import hashlib
import math
import re
import uuid
from qdrant_client import QdrantClient, models
from .catalog import POLICIES
from . import config

DIMENSIONS = 128
COLLECTION = 'assessment_policies_demo'

def vector(text):
    # Deliberately lightweight demo embeddings. Replace with a evaluated semantic encoder.
    result = [0.0] * DIMENSIONS
    for token in re.findall(r'[a-z0-9]+', text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        result[int.from_bytes(digest[:2], 'big') % DIMENSIONS] += 1 if digest[2] % 2 else -1
    norm = math.sqrt(sum(x*x for x in result)) or 1
    return [x/norm for x in result]

def seed():
    client = QdrantClient(url=config.QDRANT_URL, timeout=10)
    if not client.collection_exists(COLLECTION):
        client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=DIMENSIONS, distance=models.Distance.COSINE))
    for name in ('tenant','job_ids'):
        client.create_payload_index(COLLECTION, field_name=name, field_schema=models.PayloadSchemaType.KEYWORD)
    client.upsert(COLLECTION, points=[models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL,p['tenant']+':'+p['id'])), vector=vector(p['text']), payload=p) for p in POLICIES], wait=True)

def retrieve(tenant, job, query):
    if config.RETRIEVAL_MODE == 'qdrant':
        client = QdrantClient(url=config.QDRANT_URL, timeout=10)
        result = client.query_points(COLLECTION, query=vector(query),
            query_filter=models.Filter(must=[models.FieldCondition(key='tenant',match=models.MatchValue(value=tenant)),
                models.FieldCondition(key='job_ids',match=models.MatchValue(value=job['id']))]), limit=5, with_payload=True)
        policies = [point.payload for point in result.points]
    elif config.RETRIEVAL_MODE == 'local':
        policies = [p for p in POLICIES if p['tenant']==tenant and job['id'] in p['job_ids']]
        qv = vector(query)
        policies.sort(key=lambda p: sum(a*b for a,b in zip(qv, vector(p['text']))), reverse=True)
    else:
        raise ValueError('RETRIEVAL_MODE must be local or qdrant')
    # Enforce scope again before any document reaches the model or response.
    if any(p['tenant'] != tenant or job['id'] not in p['job_ids'] for p in policies):
        raise ValueError('Retrieval isolation violation')
    return policies

if __name__ == '__main__':
    seed()
    print('Seeded versioned synthetic policy documents')
