"""Validate account-owned registration responses before rendering or opening URLs."""
from datetime import datetime
from math import isfinite
from urllib.parse import urlsplit,unquote,quote
from uuid import UUID

from ft_tui.features.catalog.models import CatalogScope,positive

REASONS={None,'scope_missing','scope_unknown','permission_denied','eligibility_changed',
         'source_unavailable','validation_rejected','outcome_unknown','project_page_unavailable'}
OUTCOMES={'registered','already_registered','pending','rejected','outcome_unknown'}


def _require(condition):
    if not condition:
        raise ValueError('Invalid registration response')


def _date(value):
    if value is None:
        return
    _require(isinstance(value,str))
    try:
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
        _require(date.tzinfo is not None)
    except (ValueError,OverflowError):
        raise ValueError('Invalid registration timestamp') from None


def _source(value):
    _require(isinstance(value,dict))
    _require(value.get('status') in {'available','unavailable','unknown'} and type(value.get('stale')) is bool)
    _date(value.get('collected_at'))
    _require(value['status']!='available' or value.get('collected_at') is not None)
    return {k:value[k] for k in ('status','stale','collected_at')}


def _attempt(value,project_id,scope):
    if value is None:
        return None
    _require(isinstance(value,dict) and positive(value.get('id')) and value.get('project_id')==project_id)
    ids=value.get('cursus_ids')
    _require(isinstance(ids,list) and all(positive(x) for x in ids) and scope.cursus_id in ids)
    _require(all(isinstance(value.get(k),str) for k in ('slug','name','status')))
    _require(value.get('validated') is None or type(value['validated']) is bool)
    score=value.get('final_mark')
    _require(score is None or type(score) in (int,float) and isfinite(score))
    _require(value.get('vogsphere_url') is None or isinstance(value['vogsphere_url'],str))
    return {k:value.get(k) for k in ('id','project_id','slug','name','status','cursus_ids','validated','final_mark','vogsphere_url')}


def _operation(value,project_id,scope):
    if value is None:
        return None
    _require(isinstance(value,dict) and isinstance(value.get('id'),str))
    try:
        UUID(value['id'])
    except ValueError:
        raise ValueError('Invalid operation ID') from None
    _require(value.get('outcome') in OUTCOMES and value.get('reason_code') in REASONS)
    return {'id':value['id'],'outcome':value['outcome'],'reason_code':value.get('reason_code'),
            'attempt':_attempt(value.get('attempt'),project_id,scope)}


def registration_state(value:dict,project_id:int,scope:CatalogScope,account_id:str)->dict:
    _require(positive(project_id) and isinstance(value,dict) and positive(value.get('project_id')))
    _require(value['project_id']==project_id and value.get('account_id')==account_id)
    context=value.get('context')
    _require(isinstance(context,dict) and all(positive(context.get(k)) for k in ('cursus_id','campus_id')) and context==scope.params())
    relationship=value.get('relationship');eligibility=value.get('eligibility');capability=value.get('capability');sources=value.get('sources')
    _require(all(isinstance(x,dict) for x in (relationship,eligibility,capability,sources)))
    _require(relationship.get('state') in {'not_registered','registered','in_progress','completed','failed','unavailable'})
    _require(type(relationship.get('outdated')) is bool and (relationship.get('phase') is None or isinstance(relationship['phase'],str)))
    _require(eligibility.get('state') in {'available','unavailable','unknown'} and type(eligibility.get('outdated')) is bool and eligibility.get('reason_code') in REASONS)
    _require(capability.get('mode') in {'api','intra','unavailable'} and capability.get('reason_code') in REASONS)
    mode=value.get('project_mode','unknown')
    _require(mode in {'solo','group','unknown'})
    url=value.get('intra_url')
    if url is not None:
        _require(isinstance(url,str))
        parsed=urlsplit(url)
        _require(parsed.scheme=='https' and parsed.netloc=='projects.intra.42.fr' and not parsed.query and not parsed.fragment)
        if parsed.path.startswith('/projects/'):
            slug=unquote(parsed.path[len('/projects/'):])
        else:
            _require(parsed.path.startswith('/') and parsed.path.endswith('/mine'))
            slug=unquote(parsed.path[1:-len('/mine')])
        _require(bool(slug))
        _require('/' not in slug and '\\' not in slug and slug not in {'.','..'} and all(ord(c)>32 for c in slug))
        url=f'https://projects.intra.42.fr/{quote(slug,safe="")}/mine'
    return {'project_mode':mode,'account_id':account_id,'project_id':project_id,'context':scope.params(),
            'relationship':{'state':relationship['state'],'phase':relationship.get('phase'),'outdated':relationship['outdated'],
                            'attempt':_attempt(relationship.get('attempt'),project_id,scope)},
            'eligibility':{k:eligibility.get(k) for k in ('state','outdated','reason_code')},
            'capability':{k:capability.get(k) for k in ('mode','reason_code')},
            'sources':{'projects':_source(sources.get('projects')),'registration':_source(sources.get('registration'))},
            'intra_url':url,'operation':_operation(value.get('operation'),project_id,scope)}


def registration_result(value:dict,project_id:int,scope:CatalogScope,account_id:str)->dict:
    _require(isinstance(value,dict))
    state=registration_state(value.get('state'),project_id,scope,account_id)
    operation=_operation(value.get('operation'),project_id,scope)
    # A replayed request retains its original operation; state may include newer activity.
    _require(operation is not None)
    return {'state':state,'operation':operation}
