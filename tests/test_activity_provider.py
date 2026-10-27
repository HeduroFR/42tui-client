import unittest
from copy import deepcopy
from ft_tui.api.catalog_types import CatalogScope
from ft_tui.api.activity_types import project_activity, team_evaluations
from ft_tui.api.http_client import HttpProjectProvider
from activity_fixtures import history, evaluations

class ActivityProviderTests(unittest.TestCase):
    def test_friend_activity_keeps_viewer_and_subject_separate_and_rejects_mismatches(self):
        from ft_tui.api.activity_types import friend_activity,friend_evaluations
        value=history();value.update(subject_user_id='50',attempt_id=72)
        for team in value['teams']:team['members']=[{'id':50,'login':'alice','leader':True}]
        self.assertEqual(friend_activity(value,1001,72,'50',self.scope,'42')['subject_user_id'],'50')
        for field,wrong in [('subject_user_id','51'),('attempt_id',73),('account_id','99')]:
            changed=deepcopy(value);changed[field]=wrong
            with self.assertRaises(ValueError):friend_activity(changed,1001,72,'50',self.scope,'42')
        value['teams'][0]['members'][0]['id']=42
        with self.assertRaises(ValueError):friend_activity(value,1001,72,'50',self.scope,'42')
        e=evaluations();e.update(subject_user_id='50',attempt_id=72)
        self.assertEqual(friend_evaluations(e,1001,72,'50',8,self.scope,'42')['team_id'],8)
        e['attempt_id']=73
        with self.assertRaises(ValueError):friend_evaluations(e,1001,72,'50',8,self.scope,'42')
    def setUp(self): self.scope = CatalogScope(21, 31)
    def test_validates_scores_nulls_and_hidden_participants(self):
        h = project_activity(history(), 1001, self.scope, '42')
        self.assertEqual([t['final_mark'] for t in h['teams']], [125, 0])
        e = team_evaluations(evaluations(), 1001, 8, self.scope, '42')
        self.assertIsNone(e['peer']['items'][0]['corrector'])
    def test_rejects_cross_account_project_team_and_bad_metadata(self):
        for key, value in [('account_id', '99'), ('project_id', 4), ('context', {'cursus_id': 4, 'campus_id': 31})]:
            h = history(); h[key] = value
            with self.assertRaises(ValueError): project_activity(h, 1001, self.scope, '42')
        for edit in [lambda e: e.update(team_id=7), lambda e: e['peer']['items'][0].update(team_id=7),
                     lambda e: e['peer']['source'].update(collected_at='bad'),
                     lambda e: e['automated']['items'][0].update(final_mark=True)]:
            e = evaluations(); edit(e)
            with self.assertRaises(ValueError): team_evaluations(e, 1001, 8, self.scope, '42')
    def test_provider_paths_and_refresh(self):
        class API:
            calls = []
            def request(self, method, path, **kwargs):
                self.calls.append((method, path, kwargs))
                return evaluations() if path.endswith('evaluations') else history()
        api = API(); p = HttpProjectProvider(api)
        p.get_project_activity(1001, self.scope, '42', refresh=True)
        p.get_team_evaluations(1001, 8, self.scope, '42')
        self.assertEqual(api.calls[0], ('GET', '/v1/me/projects/1001/activity', {'params': {'cursus_id': 21, 'campus_id': 31, 'refresh': 'true'}}))
        self.assertEqual(api.calls[1][1], '/v1/me/projects/1001/teams/8/evaluations')
    def test_permission_reason_survives_provider_validation(self):
        e = evaluations(); e['automated']['source'] = {'status': 'unavailable', 'stale': True, 'collected_at': None, 'reason_code': 'permission_denied'}
        self.assertEqual(team_evaluations(e, 1001, 8, self.scope, '42')['automated']['source']['reason_code'], 'permission_denied')
    def test_retained_available_sources_keep_the_original_collection_date(self):
        value = evaluations(); value['peer']['source']['stale'] = True
        result = team_evaluations(value, 1001, 8, self.scope, '42')
        self.assertTrue(result['peer']['source']['stale'])
        self.assertEqual(result['peer']['source']['collected_at'], value['peer']['source']['collected_at'])
