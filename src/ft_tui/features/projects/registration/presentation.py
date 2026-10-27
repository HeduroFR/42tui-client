"""Pure registration copy and action decisions, with freshness checked at display time."""
from dataclasses import dataclass
from urllib.parse import quote
from datetime import datetime,timedelta,timezone
from ft_tui.i18n import translate


@dataclass(frozen=True)
class RegistrationView:
    relationship:str
    eligibility:str
    feedback:str
    action:str
    enabled:bool
    deadline:datetime|None


def registration_view(state:dict,*,now:datetime,language:str)->RegistrationView:
    def t(text):return translate(text,language)
    def fresh(name,seconds):
        meta=state['sources'][name]
        try:
            at=datetime.fromisoformat(meta['collected_at'].replace('Z','+00:00'))
            deadline=at+timedelta(seconds=seconds)
            return meta['status']=='available' and not meta['stale'] and at<=now+timedelta(seconds=30) and now<deadline,deadline
        except (TypeError,KeyError,ValueError,AttributeError):
            return False,None
    personal,personal_deadline=fresh('projects',900)
    eligible,eligibility_deadline=fresh('registration',300)
    relation=state['relationship'];kind=relation['state']
    if not personal and kind=='not_registered':kind='unavailable'
    label={'not_registered':'Not registered','registered':'Registered','in_progress':'In progress','completed':'Completed','failed':'Failed','unavailable':'Registration status unavailable'}[kind]
    relationship=t(label)
    if kind=='in_progress' and relation['phase']=='waiting_for_correction':relationship+=' · '+t('Awaiting correction')
    if kind=='registered' and relation['phase'] not in {'creating_group','searching_a_group','waiting_to_start'}:relationship+=' · '+t('Progress unavailable')
    if (not personal or relation['outdated']) and kind!='unavailable':relationship+=' · '+t('Last known · outdated')
    eligibility=t('Available to register' if eligible and state['eligibility']['state']=='available' else 'Eligibility unconfirmed · 42 will validate registration' if eligible else 'Eligibility outdated' if state['sources']['registration'].get('collected_at') else 'Eligibility unavailable')
    if kind=='completed':eligibility=''
    action='none';enabled=False;feedback=''
    op=state.get('operation')
    if op and op['outcome'] in {'pending','outcome_unknown'}:
        action='refresh';enabled=True
        feedback=t('Registration outcome unknown. Refresh status before trying again.' if op['outcome']=='outcome_unknown' else 'Registration is pending. Refresh status to check the result.')
    elif kind in {'not_registered','unavailable'}:
        if not personal or relation['outdated']:
            action='refresh';enabled=True
        else:
            action='register'
            enabled=state['capability']['mode']=='api'
            if not enabled:
                feedback=t('Refresh the project catalog before registering.' if state['capability'].get('reason_code')=='source_unavailable' else '42 API registration permission is unavailable. Reconnect your account with the projects scope.')
    if op and op['outcome']=='rejected' and kind in {'not_registered','unavailable'}:
        feedback=t({'permission_denied':'42 API registration permission is unavailable. Reconnect your account with the projects scope.',
                    'eligibility_changed':'Registration eligibility changed. Refresh status.',
                    'validation_rejected':'42 rejected registration without a confirmed reason.'}.get(op['reason_code'],'Registration was not submitted. Refresh status.'))
    deadlines=[d for d in (personal_deadline,eligibility_deadline) if d and d>now]
    return RegistrationView(relationship,eligibility,feedback,action,enabled,min(deadlines) if deadlines else None)


def cached_registration_state(project,curriculum,account_id,scope):
    """Project an owned cached observation conservatively while the network loads."""
    owned=curriculum.get('account_id')==account_id
    unknown={'status':'unknown','stale':True,'collected_at':None}
    sources=curriculum.get('sources',{}) if owned else {}
    projects=sources.get('projects',unknown)
    registration=curriculum.get('registration',unknown) if owned else unknown
    attempt=project.progress_data if owned else {}
    if not attempt.get('id') or scope.cursus_id not in attempt.get('cursus_ids',[]):
        attempt=None
    kind='unavailable'
    if attempt:
        raw=attempt.get('status')
        kind=('completed' if attempt.get('validated') is True else 'failed' if attempt.get('validated') is False else 'registered') if raw=='finished' else 'in_progress' if raw in {'in_progress','waiting_for_correction'} else 'registered'
    elif projects.get('status')=='available' and not projects.get('stale',True):
        kind='not_registered'
    return {'project_mode':project.catalog_data.get('project_mode','unknown'),'account_id':account_id,'project_id':project.official_project_id,'context':scope.params(),
            'relationship':{'state':kind,'phase':attempt.get('status') if attempt else None,'attempt':attempt,'outdated':projects.get('stale',True)},
            'eligibility':{'state':'available' if registration.get('status')=='available' and project.official_project_id in registration.get('project_ids',[]) else 'unavailable' if registration.get('status')=='available' else 'unknown','outdated':registration.get('stale',True),'reason_code':None},
            'capability':{'mode':'intra','reason_code':'scope_unknown'},'sources':{'projects':projects,'registration':{k:registration.get(k) for k in ('status','stale','collected_at')}},
            'intra_url':f'https://projects.intra.42.fr/{quote(project.slug,safe="")}/mine' if project.slug else None,'operation':None}
