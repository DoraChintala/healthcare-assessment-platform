"""Measure queue-inclusive automated latency; final human review is excluded."""
import argparse,json,statistics,time,uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://localhost:8080/api')
parser.add_argument('--token',default='local-demo-reviewer-token')
parser.add_argument('--profiles',type=int,default=20)
parser.add_argument('--concurrency',type=int,default=4)
args=parser.parse_args()
def call(method,path,body=None,key=None):
    headers={'Authorization':'Bearer '+args.token,'Content-Type':'application/json'}
    if key:headers['Idempotency-Key']=key
    req=Request(args.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    with urlopen(req,timeout=20) as response:return json.load(response)

def profile(_):
    start=time.monotonic()
    row=call('POST','/assessments',{'resume_text':'Experience: 5 years\nLicense: DEMO-VA-1001\nState: VA','job_id':'rn-icu'},str(uuid.uuid4()))
    while time.monotonic()-start<120:
        row=call('GET','/assessments/'+row['id'])
        if row['status']=='AWAITING_APPROVAL':return time.monotonic()-start
        if row['status'] in ('FAILED','AWAITING_CLARIFICATION'):raise RuntimeError('Unexpected outcome: '+row['status'])
        time.sleep(.25)
    raise TimeoutError('Assessment did not finish within 120 seconds')

start=time.monotonic()
with ThreadPoolExecutor(max_workers=args.concurrency) as pool:latencies=list(pool.map(profile,range(args.profiles)))
elapsed=time.monotonic()-start
ordered=sorted(latencies)
print(json.dumps({'profiles':len(latencies),'concurrency':args.concurrency,'p50_seconds':statistics.median(latencies),'p95_seconds':ordered[max(0,int(.95*len(ordered)+.999)-1)],'successful_profiles_per_minute':len(latencies)/elapsed*60,'latency_scope':'submission through ready-for-review; includes queue delay; excludes human review; includes polling granularity'},indent=2))
