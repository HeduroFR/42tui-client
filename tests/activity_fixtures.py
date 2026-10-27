from copy import deepcopy
SOURCE = {'status': 'available', 'stale': False, 'collected_at': '2026-10-22T10:00:00Z'}
CONTEXT = {'cursus_id': 21, 'campus_id': 31}
TEAM = {'id': 8, 'project_id': 1001, 'name': "student's group", 'status': 'finished', 'final_mark': 125,
        'validated': True, 'created_at': '2026-10-22T09:00:00Z', 'locked_at': None, 'closed_at': None,
        'repo_url': None, 'members': [{'id': 42, 'login': 'student', 'leader': True}]}
PEER = {'id': 1, 'team_id': 8, 'corrector': None, 'participants_hidden': True,
        'begin_at': '2026-12-01T10:00:00Z', 'filled_at': None, 'final_mark': None,
        'comment': '[red]literal', 'feedback': None, 'feedback_rating': None, 'flag': None, 'feedbacks': []}
def history():
    return deepcopy({'account_id': '42', 'project_id': 1001, 'context': CONTEXT, 'current_team_id': 8,
                     'teams': [TEAM, {**TEAM, 'id': 7, 'final_mark': 0, 'validated': False}], 'source': SOURCE})
def evaluations(team_id=8):
    return deepcopy({'account_id': '42', 'project_id': 1001, 'context': CONTEXT, 'team_id': team_id,
                     'peer': {'items': [{**PEER, 'team_id': team_id}], 'source': SOURCE},
                     'automated': {'items': [{'id': 2, 'name': 'Moulinette', 'created_at': None,
                                              'final_mark': 0, 'comment': 'test: KO\n[bold]literal'}], 'source': SOURCE}})
