"""Validate account-owned project activity and discard unrecognized upstream fields."""
from datetime import datetime
from math import isfinite
from ft_tui.features.catalog.models import positive


def require(condition):
    if not condition:
        raise ValueError('Invalid project activity response')


def text(value):
    require(value is None or isinstance(value, str) and len(value) <= 1048576)
    return value


def date(value):
    if value is not None:
        require(isinstance(value, str))
        try:
            require(datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None)
        except (ValueError, OverflowError):
            raise ValueError('Invalid project activity timestamp') from None
    return value


def mark(value):
    require(value is None or type(value) in (int, float) and isfinite(value))
    return value


def source(value):
    require(isinstance(value, dict))
    require(value.get('status') in {'available', 'unavailable', 'unknown'} and type(value.get('stale')) is bool)
    at = date(value.get('collected_at'))
    require(value['status'] != 'available' or at is not None)
    reason = value.get('reason_code')
    require(reason in (None, 'permission_denied'))
    return {'status': value['status'], 'stale': value['stale'], 'collected_at': at,
            **({'reason_code': reason} if reason else {})}


def rows(value):
    require(isinstance(value, list) and len(value) <= 10000)
    require(all(isinstance(x, dict) and positive(x.get('id')) for x in value))
    require(len({x['id'] for x in value}) == len(value))
    return value


def identity(value, project_id, scope, account_id):
    require(positive(project_id) and isinstance(value, dict))
    require(value.get('account_id') == account_id and value.get('project_id') == project_id)
    require(value.get('context') == scope.params())
    return {'account_id': account_id, 'project_id': project_id, 'context': scope.params()}


def project_activity(value, project_id, scope, account_id, *, subject_user_id=None):
    result = identity(value, project_id, scope, account_id)
    require(value.get('current_team_id') is None or positive(value['current_team_id']))
    teams = []
    for team in rows(value.get('teams')):
        require(team.get('project_id') == project_id)
        require(isinstance(team.get('name'), str) and isinstance(team.get('status'), str))
        require(team.get('validated') is None or type(team['validated']) is bool)
        members = []
        for member in rows(team.get('members')):
            require(isinstance(member.get('login'), str) and type(member.get('leader')) is bool)
            members.append({k: member[k] for k in ('id', 'login', 'leader')})
        require(any(str(m['id']) == (subject_user_id or account_id) for m in members))
        teams.append({'id': team['id'], 'project_id': project_id, 'name': team['name'], 'status': team['status'],
                      'validated': team.get('validated'), 'final_mark': mark(team.get('final_mark')),
                      'repo_url': text(team.get('repo_url')), 'members': members,
                      **{k: date(team.get(k)) for k in ('created_at', 'locked_at', 'closed_at')}})
    return {**result, 'current_team_id': value.get('current_team_id'), 'teams': teams, 'source': source(value.get('source'))}


def team_evaluations(value, project_id, team_id, scope, account_id):
    result = identity(value, project_id, scope, account_id)
    require(positive(team_id) and value.get('team_id') == team_id)
    groups = {}
    for name in ('peer', 'automated'):
        group = value.get(name)
        require(isinstance(group, dict))
        items = []
        for item in rows(group.get('items')):
            clean = {'id': item['id'], 'final_mark': mark(item.get('final_mark')), 'comment': text(item.get('comment'))}
            if name == 'automated':
                require(isinstance(item.get('name'), str))
                clean.update(name=item['name'], created_at=date(item.get('created_at')))
            else:
                require(item.get('team_id') is None or item['team_id'] == team_id)
                require(type(item.get('details_unavailable', False)) is bool)
                corrector = item.get('corrector')
                require(corrector is None or isinstance(corrector, dict) and positive(corrector.get('id')) and isinstance(corrector.get('login'), str))
                require(type(item.get('participants_hidden')) is bool)
                flag = item.get('flag')
                require(flag is None or isinstance(flag, dict) and isinstance(flag.get('name'), str) and (flag.get('positive') is None or type(flag['positive']) is bool))
                feedbacks = item.get('feedbacks')
                require(isinstance(feedbacks, list) and len(feedbacks) <= 1000)
                require(all(isinstance(f, dict) for f in feedbacks))
                clean.update(details_unavailable=item.get('details_unavailable', False), team_id=item.get('team_id'), corrector={k: corrector[k] for k in ('id', 'login')} if corrector else None,
                             participants_hidden=item['participants_hidden'], begin_at=date(item.get('begin_at')),
                             filled_at=date(item.get('filled_at')), feedback=text(item.get('feedback')),
                             feedback_rating=mark(item.get('feedback_rating')), flag=flag,
                             feedbacks=[{'comment': text(f.get('comment')), 'rating': mark(f.get('rating'))} for f in feedbacks])
            items.append(clean)
        groups[name] = {'items': items, 'source': source(group.get('source'))}
    return {**result, 'team_id': team_id, **groups}


def friend_activity(value, project_id, attempt_id, user_id, scope, account_id):
    require(isinstance(value,dict) and value.get('subject_user_id')==user_id and value.get('attempt_id')==attempt_id)
    clean=project_activity(value,project_id,scope,account_id,subject_user_id=user_id)
    require(clean['current_team_id'] is None or any(team['id']==clean['current_team_id'] for team in clean['teams']))
    return {**clean,'subject_user_id':user_id,'attempt_id':attempt_id}


def friend_evaluations(value, project_id, attempt_id, user_id, team_id, scope, account_id):
    require(isinstance(value,dict) and value.get('subject_user_id')==user_id and value.get('attempt_id')==attempt_id)
    return {**team_evaluations(value,project_id,team_id,scope,account_id),'subject_user_id':user_id,'attempt_id':attempt_id}
