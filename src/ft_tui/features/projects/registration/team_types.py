"""Strict account and project boundary for team management responses."""
from ft_tui.features.catalog.models import positive


def team_state(value, project_id, scope, account_id):
    if (not isinstance(value, dict) or value.get('account_id') != account_id
            or value.get('project_id') != project_id or value.get('context') != scope.params()
            or type(value.get('can_write')) is not bool or not isinstance(value.get('teams'), list)):
        raise ValueError('Team response identity mismatch')
    session = value.get('session')
    if session is not None and (not isinstance(session, dict) or not positive(session.get('id'))
            or session.get('project_id') != project_id or type(session.get('solo')) is not bool
            or session.get('max_people') is not None and not positive(session['max_people'])
            or session.get('campus_id') not in (None, scope.campus_id)
            or session.get('cursus_id') not in (None, scope.cursus_id)):
        raise ValueError('Invalid team session')
    ids = set()
    for team in value['teams']:
        if (not isinstance(team, dict) or not positive(team.get('id')) or team['id'] in ids
                or team.get('project_id') != project_id or not positive(team.get('project_session_id'))
                or not isinstance(team.get('name'), str) or not isinstance(team.get('status'), str)
                or type(team.get('locked')) is not bool or type(team.get('closed')) is not bool
                or not isinstance(team.get('members'), list)):
            raise ValueError('Invalid team')
        ids.add(team['id'])
        members = set()
        for member in team['members']:
            if (not isinstance(member, dict) or not positive(member.get('id')) or member['id'] in members
                    or not isinstance(member.get('login'), str) or type(member.get('leader')) is not bool
                    or type(member.get('accepted')) is not bool):
                raise ValueError('Invalid member')
            members.add(member['id'])
        if int(account_id) not in members:
            raise ValueError('Unrelated team')
    return value
