import logging
import threading
import time
from contextlib import contextmanager
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from sqlalchemy import update
from . import config, store
from .workflow import build_graph
from .metrics import ATTEMPTS, ATTEMPT_SECONDS

logger = logging.getLogger('assessment.worker')

@contextmanager
def graph_context():
    if config.CHECKPOINT_URL:
        with PostgresSaver.from_conn_string(config.CHECKPOINT_URL) as saver:
            saver.setup()
            yield build_graph(saver)
    else:
        with SqliteSaver.from_conn_string(str(config.DATA_DIR/'checkpoints.db')) as saver:
            yield build_graph(saver)

def heartbeat(job, stop):
    while not stop.wait(20):
        with store.Session() as db:
            db.execute(update(store.Assessment).where(store.Assessment.id==job['id'],store.Assessment.lease_owner==job['owner'],store.Assessment.status=='PROCESSING').values(lease_until=time.time()+config.LEASE_SECONDS))
            db.commit()

def process_one(graph):
    job = store.claim()
    if not job:
        return False
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat,args=(job,stop),daemon=True)
    thread.start()
    started = time.monotonic()
    settings = {'configurable':{'thread_id':job['tenant']+':'+job['id']},'recursion_limit':30}
    try:
        snapshot = graph.get_state(settings)
        pending = any(getattr(task,'interrupts',()) for task in snapshot.tasks)
        reply = job['resume']
        if not snapshot.values:
            graph.invoke({'tenant':job['tenant'], **job['request']},settings)
        elif reply and snapshot.values.get('applied_resume_id') != reply['resume_id']:
            if not pending:
                raise ValueError('Clarification command has no matching interrupt')
            graph.invoke(Command(resume=reply),settings)
        elif snapshot.next and not pending:
            # Resume unfinished work after a crash, rather than redoing extraction.
            graph.invoke(None,settings)
        state = dict(graph.get_state(settings).values)
        store.finish(job,state)
        ATTEMPTS.labels('clarification' if state.get('needs_clarification') else 'ready_for_review').inc()
    except Exception as exc:
        # Do not log model responses, resume text, tokens, or exception messages with sensitive data.
        logger.warning('assessment=%s error_type=%s',job['id'],type(exc).__name__)
        store.finish(job,{},error='Processing dependency or validation failure; inspect service health and retry configuration')
        ATTEMPTS.labels('error').inc()
    finally:
        stop.set()
        thread.join(timeout=2)
        ATTEMPT_SECONDS.observe(time.monotonic()-started)
    return True

def run(stop=None):
    stop = stop or threading.Event()
    store.init_db()
    with graph_context() as graph:
        while not stop.is_set():
            try:
                busy = process_one(graph)
            except Exception as exc:
                logger.warning('queue error_type=%s',type(exc).__name__)
                busy = False
            stop.wait(.1 if busy else .5)

if __name__ == '__main__':
    from prometheus_client import start_http_server
    start_http_server(9000)
    logging.basicConfig(level=logging.INFO)
    run()
