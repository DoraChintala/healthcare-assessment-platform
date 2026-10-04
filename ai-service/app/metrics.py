import time
from functools import wraps
from prometheus_client import Histogram, Counter

NODE_SECONDS = Histogram('assessment_node_seconds','Duration of a workflow node execution',['node'])
ATTEMPTS = Counter('assessment_worker_attempts_total','Worker processing attempts',['outcome'])
ATTEMPT_SECONDS = Histogram('assessment_worker_attempt_seconds','Automated worker attempt time, excluding human wait')

def measured(name, function):
    @wraps(function)
    def wrapper(state):
        started=time.monotonic()
        try:
            return function(state)
        finally:
            NODE_SECONDS.labels(name).observe(time.monotonic()-started)
    return wrapper
