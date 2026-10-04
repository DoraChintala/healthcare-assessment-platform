from qdrant_client import QdrantClient, models
from app.retrieval import retrieve,vector,DIMENSIONS,COLLECTION
from app.catalog import JOBS
from app import config

def test_local_retrieval_is_scoped():
    results=retrieve('demo-hospital',JOBS['rn-icu'],'RN license ICU')
    assert {p['id'] for p in results}=={'policy-rn','policy-icu'}
    assert retrieve('unknown-tenant',JOBS['rn-icu'],'RN license')==[]

def test_qdrant_filters_exclude_other_tenants(monkeypatch):
    client=QdrantClient(':memory:')
    client.create_collection(COLLECTION,vectors_config=models.VectorParams(size=DIMENSIONS,distance=models.Distance.COSINE))
    docs=[{'id':'policy-rn','tenant':'demo-hospital','job_ids':['rn-icu'],'text':'registered nurse'},
          {'id':'private-policy','tenant':'other-hospital','job_ids':['rn-icu'],'text':'registered nurse'}]
    client.upsert(COLLECTION,[models.PointStruct(id=i+1,vector=vector(d['text']),payload=d) for i,d in enumerate(docs)])
    monkeypatch.setattr(config,'RETRIEVAL_MODE','qdrant')
    monkeypatch.setattr('app.retrieval.QdrantClient',lambda **kwargs:client)
    assert [p['id'] for p in retrieve('demo-hospital',JOBS['rn-icu'],'registered nurse')]==['policy-rn']

