from datetime import date
from .catalog import REGISTRY
from .models import Candidate, Summary

RULES_VERSION = 'rules-demo-1'

def evaluate(candidate: Candidate, job):
    rules = []
    def add(rule_id, status, reason, source):
        rules.append({'id':rule_id,'status':status,'reason':reason,'source':source})
    if candidate.years_experience is None:
        add('experience','UNKNOWN','Experience claim missing','resume')
    elif candidate.years_experience < job['minimum_years']:
        add('experience','FAIL',f"Claimed experience is below {job['minimum_years']} years",'resume')
    else:
        add('experience','PASS','Experience claim meets the threshold; employment history is not independently verified','resume')
    record = next((r for r in REGISTRY if r['license_number']==candidate.license_number and r['state']==candidate.license_state), None)
    if not record:
        add('license','UNKNOWN','No matching simulated registry record; verification pending','SIMULATED_REGISTRY')
    elif record['state'] != job['license_state'] or record['credential'] != 'RN':
        add('license','FAIL','Registry credential does not match the required state/type','SIMULATED_REGISTRY')
    elif record['status'] != 'ACTIVE' or date.fromisoformat(record['expires_on']) < date.today():
        add('license','FAIL','Simulated registry license is expired or inactive','SIMULATED_REGISTRY')
    else:
        add('license','PASS','License active in the simulated registry only','SIMULATED_REGISTRY')
    return rules, record

def summary_for(rules, policies):
    # The authoritative recommendation is derived from rules, never model self-confidence.
    statuses = {rule['status'] for rule in rules}
    recommendation = 'VERIFICATION_PENDING' if 'UNKNOWN' in statuses else ('REQUIREMENTS_NOT_MET' if 'FAIL' in statuses else 'REQUIREMENTS_MET')
    text = ' '.join(rule['reason'] + '.' for rule in rules)
    text += ' Human approval is required. Registry data is simulated; this is not real credential verification.'
    return Summary(text=text, recommendation=recommendation, rule_ids=[r['id'] for r in rules], policy_ids=[p['id'] for p in policies])
