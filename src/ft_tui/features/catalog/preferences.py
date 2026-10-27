"""Resolve track preferences and automatic personal ranks without mixing tracks."""
from hashlib import sha256

def preference_key(account,cursus,campus,name):
    owner=sha256(str(account).encode()).hexdigest()[:24]
    return f'catalog_{name}_{owner}_{cursus}_{campus}'

def select_track(evidence,preference):
    if evidence.get('source') in ('quest','project') and evidence.get('track') in ('old','new') and not evidence.get('conflict'):
        return {'track':evidence['track'],'source':evidence['source'],'conflict':False}
    if preference in ('old','new'):
        return {'track':preference,'source':'manual','conflict':bool(evidence.get('conflict'))}
    if evidence.get('source')=='cohort' and evidence.get('track') in ('old','new'):
        return {'track':evidence['track'],'source':'cohort','conflict':False}
    return {'track':None,'source':'unknown','conflict':bool(evidence.get('conflict'))}

def select_rank(evidence):
    if type(evidence.get('rank')) is int and evidence.get('source')=='quest':return evidence
    if type(evidence.get('rank')) is int and 0 <= evidence['rank'] <= 6 and evidence.get('source') == 'project':
        return {**evidence,'completed':False}
    return {'rank':None,'source':'unknown','completed':False}
