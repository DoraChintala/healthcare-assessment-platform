import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, UniqueConstraint, select, update, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import IntegrityError
from . import config

class Base(DeclarativeBase):
    pass

class Assessment(Base):
    __tablename__ = 'assessments'
    __table_args__ = (UniqueConstraint('tenant', 'idempotency_key'),)
    id = Column(String(36), primary_key=True)
    tenant = Column(String(100), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    request_json = Column(Text, nullable=False)
    status = Column(String(40), nullable=False, index=True)
    version = Column(Integer, default=0, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    resume_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error = Column(String(200), nullable=True)
    lease_until = Column(Float, nullable=True)
    lease_owner = Column(String(36), nullable=True)
    created_at = Column(String(40), nullable=False)
    updated_at = Column(String(40), nullable=False)

class Audit(Base):
    __tablename__ = 'audit_events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(String(36), nullable=False, index=True)
    tenant = Column(String(100), nullable=False)
    action = Column(String(60), nullable=False)
    actor = Column(String(100), nullable=False)
    detail_json = Column(Text, nullable=False)
    created_at = Column(String(40), nullable=False)

engine = create_engine(config.DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 30} if config.DATABASE_URL.startswith('sqlite') else {}, pool_pre_ping=True)
if config.DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_config(connection, _):
        connection.execute('PRAGMA journal_mode=WAL')
Session = sessionmaker(bind=engine, expire_on_commit=False)

def now():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    Base.metadata.create_all(engine)

def add_audit(db, row, action, actor, detail):
    db.add(Audit(assessment_id=row.id, tenant=row.tenant, action=action, actor=actor, detail_json=json.dumps(detail), created_at=now()))

def public(row):
    return {'id': row.id, 'job_id': json.loads(row.request_json)['job_id'], 'status': row.status, 'version': row.version,
            'attempts': row.attempts, 'result': json.loads(row.result_json) if row.result_json else None,
            'error': row.error, 'created_at': row.created_at, 'updated_at': row.updated_at}

def create(tenant, key, body, actor):
    encoded = json.dumps(body, sort_keys=True)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    with Session() as db:
        row = db.scalar(select(Assessment).where(Assessment.tenant == tenant, Assessment.idempotency_key == key))
        if row:
            if row.request_hash != digest:
                raise ValueError('Idempotency key already used for a different request')
            return public(row)
        row = Assessment(id=str(uuid.uuid4()), tenant=tenant, idempotency_key=key, request_hash=digest,
                         request_json=encoded, status='QUEUED', created_at=now(), updated_at=now())
        db.add(row)
        try:
            db.flush()
            add_audit(db, row, 'ASSESSMENT_CREATED', actor, {'job_id': body['job_id']})
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Assessment).where(Assessment.tenant == tenant, Assessment.idempotency_key == key))
            if not existing or existing.request_hash != digest:
                raise ValueError('Idempotency conflict')
            return public(existing)
        return public(row)

def get(tenant, assessment_id):
    with Session() as db:
        row = db.scalar(select(Assessment).where(Assessment.id == assessment_id, Assessment.tenant == tenant))
        return public(row) if row else None

def list_assessments(tenant):
    with Session() as db:
        return [public(row) for row in db.scalars(select(Assessment).where(Assessment.tenant == tenant).order_by(Assessment.created_at.desc()).limit(100))]

def audit(tenant, assessment_id):
    with Session() as db:
        return [{'action': row.action, 'actor': row.actor, 'detail': json.loads(row.detail_json), 'created_at': row.created_at}
                for row in db.scalars(select(Audit).where(Audit.tenant == tenant, Audit.assessment_id == assessment_id).order_by(Audit.id))]

def review(tenant, assessment_id, actor, body):
    with Session() as db:
        row = db.scalar(select(Assessment).where(Assessment.id == assessment_id, Assessment.tenant == tenant))
        if row is None:
            raise LookupError('Assessment not found')
        if row.version != body['expected_version']:
            raise ValueError('Assessment changed; refresh before reviewing')
        action = body['action']
        if action == 'clarify' and row.status != 'AWAITING_CLARIFICATION':
            raise ValueError('Assessment is not awaiting clarification')
        if action in ('approve', 'reject') and row.status != 'AWAITING_APPROVAL':
            raise ValueError('Assessment is not awaiting approval')
        new_status = 'QUEUED' if action == 'clarify' else 'COMPLETED'
        values = {'status': new_status, 'version': row.version + 1, 'updated_at': now()}
        if action == 'clarify':
            values.update(resume_json=json.dumps({'corrections': body['corrections'], 'notes': body['notes'], 'resume_id': str(uuid.uuid4())}), attempts=0)
        else:
            result = json.loads(row.result_json)
            result['decision'] = {'action': action, 'notes': body['notes'], 'reviewer': actor, 'at': now()}
            values['result_json'] = json.dumps(result)
        changed = db.execute(update(Assessment).where(Assessment.id == row.id, Assessment.version == row.version, Assessment.status == row.status).values(**values))
        if changed.rowcount != 1:
            raise ValueError('Concurrent review; refresh before retrying')
        add_audit(db, row, 'REVIEW_' + action.upper(), actor, {'notes': body['notes'], 'corrections': body['corrections']})
        db.commit()
    return get(tenant, assessment_id)

def claim():
    # Compare-and-set also works in SQLite; PostgreSQL avoids hot-row contention with SKIP LOCKED.
    with Session() as db:
        query = select(Assessment).where((Assessment.status == 'QUEUED') | ((Assessment.status == 'PROCESSING') & (Assessment.lease_until < time.time()))).order_by(Assessment.created_at).limit(1)
        if not config.DATABASE_URL.startswith('sqlite'):
            query = query.with_for_update(skip_locked=True)
        row = db.scalar(query)
        if not row:
            return None
        if row.attempts >= config.MAX_ATTEMPTS:
            row.status, row.error = 'FAILED', 'Processing retry limit reached'
            row.version += 1
            row.updated_at = now()
            add_audit(db, row, 'PROCESSING_FAILED', 'worker', {'reason': row.error})
            db.commit()
            return None
        owner = str(uuid.uuid4())
        attempt = row.attempts + 1
        changed = db.execute(update(Assessment).where(Assessment.id == row.id, Assessment.version == row.version).values(
            status='PROCESSING', version=row.version + 1, attempts=attempt,
            lease_until=time.time() + config.LEASE_SECONDS, lease_owner=owner, updated_at=now()))
        if changed.rowcount != 1:
            db.rollback()
            return None
        add_audit(db, row, 'PROCESSING_STARTED', 'worker', {'attempt': attempt})
        db.commit()
        return {'id': row.id, 'tenant': row.tenant, 'request': json.loads(row.request_json), 'owner': owner,
                'resume': json.loads(row.resume_json) if row.resume_json else None}

def finish(job, state, error=None):
    with Session() as db:
        row = db.scalar(select(Assessment).where(Assessment.id == job['id']))
        if not row or row.lease_owner != job['owner'] or row.status != 'PROCESSING':
            return
        # Do not clear a resume command until it has been successfully checkpointed.
        if error:
            status = 'FAILED' if row.attempts >= config.MAX_ATTEMPTS else 'QUEUED'
            row.error = error
        else:
            status = 'AWAITING_CLARIFICATION' if state.get('needs_clarification') else 'AWAITING_APPROVAL'
            row.result_json = json.dumps(state)
            row.resume_json = None
            row.error = None
        row.status = status
        row.version += 1
        row.lease_until = row.lease_owner = None
        row.updated_at = now()
        add_audit(db, row, status, 'worker', {'rules_version': state.get('rules_version'), 'error': error})
        db.commit()
