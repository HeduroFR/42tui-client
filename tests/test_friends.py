import unittest
from copy import deepcopy
from sqlalchemy import select
from ft_tui.features.friends.models import friend_snapshot
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Friend, FriendProjectProgress, FriendWatch, Project
from ft_tui.features.friends.adapters.storage import cached_observations, comparison, level_rankings, memberships, ongoing, remove_friend, save_observation
from tests.friends_fixtures import snapshot, attempt


class FriendContractTests(unittest.TestCase):
    def test_school_life_fields_accept_zero_and_reject_malformed_values(self):
        data=snapshot()
        data.update(wallet=0,correction_point=0,achievements_count=0,pool_month='september',pool_year='2026',coalitions=[{'id':7,'name':'Analysts'}])
        self.assertIs(friend_snapshot(data,'alice',21),data)
        for key,value in (('wallet',True),('correction_point',-1),('achievements_count',1.5),
                          ('xp_progress',{'total_xp':9,'level_start_xp':10,'next_level_xp':20}),('pool_month',{}),('titles',[{}]),('coalitions',[{'id':0,'name':'Analysts'}]),
                          ('coalitions',[{'id':7,'name':'Analysts'}]*2)):
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                friend_snapshot({**data,key:value},'alice',21)

    def test_provider_checks_scope_and_preserves_nullable_and_zero_marks(self):
        class API:
            def request(self, method, path, **kwargs):
                self.call = (method, path, kwargs)
                return snapshot(items=[attempt(status='finished', validated=False, mark=0)])
        api = API()
        data = HttpProjectProvider(api).get_friend('alice', 21, refresh=True)
        self.assertEqual(data['items'][0]['final_mark'], 0)
        self.assertEqual(api.call, ('GET', '/v1/friends/alice', {'params': {'cursus_id': 21, 'refresh': 'true'}, 'timeout': 180.0}))
        for login in ('', '.', '..', '  ', 'a\nb', 'x' * 101):
            with self.assertRaises(ValueError):
                HttpProjectProvider(api).get_friend(login, 21)

    def test_rejects_mixed_scope_duplicate_attempts_and_malformed_metadata(self):
        valid = snapshot()
        mutations = [lambda d: d.update(login='bob'), lambda d: d.update(cursus_id=9),
            lambda d: d.update(user_id='0'), lambda d: d.update(level=True),
            lambda d: d['items'].append(deepcopy(d['items'][0])),
            lambda d: d['items'][0].update(cursus_ids=[9]),
            lambda d: d['items'][0].update(final_mark=float('nan')),
            lambda d: d['meta'].update(cached_at='yesterday'),
            lambda d: d['presence'].update(status='unavailable')]
        for change in mutations:
            data = deepcopy(valid)
            change(data)
            with self.assertRaises(ValueError):
                friend_snapshot(data, 'alice', 21)

    def test_comparison_uses_official_ids_and_latest_attempt_and_rank_ties(self):
        mine = [attempt(), attempt(2, id=2, name='Libft', status='finished', validated=True, mark=125)]
        theirs = [attempt(id=3, status='finished', validated=True, mark=100), attempt(2, id=4, name='Renamed libft')]
        groups = comparison(mine, theirs)
        self.assertEqual([p['project_id'] for p in groups['Could help me']], [1001])
        self.assertEqual([p['project_id'] for p in groups['I could help']], [2])
        self.assertFalse(groups['Together'])
        self.assertFalse(ongoing([attempt(id=1), attempt(id=2, status='finished', validated=False, mark=0)]))
        ranked = level_rankings([snapshot('bob', user_id='51'), snapshot(), snapshot('you', user_id='42', level=0), snapshot('unknown', user_id='52', level=None)])
        self.assertEqual([(r, d['login']) for r, d in ranked], [(1, 'alice'), (1, 'bob'), (3, 'you'), (None, 'unknown')])


class FriendStorageTests(unittest.TestCase):
    def setUp(self):
        self.factory = make_session_factory('sqlite://')

    def tearDown(self):
        self.factory.kw['bind'].dispose()

    def test_legacy_watches_preserve_notes_without_fabricating_consent(self):
        with self.factory() as session:
            project = Project(slug='libft', name='Libft')
            friend = Friend(login='alice')
            session.add_all([project, friend]); session.flush()
            session.add(FriendProjectProgress(friend_id=friend.id, project_id=project.id, status='completed'))
            session.commit()
            self.assertEqual(memberships(session, '42'), [])
            self.assertEqual(memberships(session, '43'), [])
            remove_friend(session, '42', 'alice')
            self.assertEqual(memberships(session, '42'), [])
            self.assertIsNotNone(session.scalar(select(FriendProjectProgress)))

    def test_observations_are_isolated_and_presence_is_not_restored_from_disk(self):
        with self.factory() as session:
            from ft_tui.features.friends.adapters.storage import cache_mutual_friends
            cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
            save_observation(session, '42', snapshot())
            self.assertEqual(cached_observations(session, '43', 21), {})
            self.assertEqual(cached_observations(session, '42', 9), {})
            data = cached_observations(session, '42', 21)['alice']
            self.assertIsNone(data['location'])
            self.assertEqual(data['presence']['status'], 'unavailable')
            with self.assertRaises(ValueError):
                save_observation(session, '42', snapshot(user_id='51'))
            self.assertEqual(cached_observations(session, '42', 21)['alice']['user_id'], '50')
            remove_friend(session, '43', 'alice')
            self.assertEqual(len(memberships(session, '42')), 1)


class FriendCurriculumRankTests(unittest.TestCase):
    def test_project_ranking_counts_unique_validations_with_ties_and_zero(self):
        from ft_tui.features.friends.adapters.storage import project_rankings, validated_project_count
        alice = snapshot(items=[attempt(id=1, validated=True), attempt(id=2, validated=True),
                                attempt(2, id=3, validated=False)])
        bob = snapshot('bob', user_id='51', items=[attempt(validated=True)])
        zero = snapshot('zero', user_id='52', items=[])
        self.assertEqual(validated_project_count(alice), 1)
        self.assertEqual([(rank, d['login']) for rank, d in project_rankings([zero, bob, alice])],
                         [(1, 'alice'), (1, 'bob'), (3, 'zero')])
        # The most recent snapshot wins before scores are compared.
        older = deepcopy(alice)
        older['meta']['cached_at'] = '2000-01-01T00:00:00+00:00'
        older['items'].append(attempt(3, id=4, validated=True))
        self.assertEqual(len(project_rankings([older, alice])), 1)
        self.assertEqual(validated_project_count(project_rankings([older, alice])[0][1]), 1)

    def test_rank_leaderboard_uses_working_curriculum_with_ties_and_unknowns(self):
        from tests.friends_fixtures import curriculum_rank
        from ft_tui.features.friends.adapters.storage import curriculum_rankings
        rows = [snapshot('old', user_id='50', level=20), snapshot('new', user_id='51', level=1),
                snapshot('zero', user_id='52', level=9), snapshot('unknown', user_id='53', level=99)]
        rows[0]['curriculum_rank'] = curriculum_rank(3, 'old')
        rows[1]['curriculum_rank'] = curriculum_rank(3, 'new')
        rows[2]['curriculum_rank'] = curriculum_rank(0)
        higher = snapshot('higher', user_id='54', level=0)
        higher['curriculum_rank'] = curriculum_rank(4, 'new')
        rows.append(higher)
        self.assertEqual([(rank, d['login']) for rank, d in curriculum_rankings(rows)], [(1, 'higher'), (2, 'old'), (2, 'new'), (4, 'zero'), (None, 'unknown')])

    def test_snapshot_rejects_invented_or_unrelated_rank_evidence_and_accepts_rank_zero(self):
        from tests.friends_fixtures import curriculum_rank
        value = snapshot(); value['curriculum_rank'] = curriculum_rank(0)
        self.assertEqual(friend_snapshot(value, 'alice', 21)['curriculum_rank']['rank'], 0)
        for mutation in [dict(rank=True), dict(rank=-1), dict(track='invented'), dict(status='ambiguous'), dict(project_ids=[999]), dict(stale='yes')]:
            invalid = deepcopy(value); invalid['curriculum_rank'].update(mutation)
            with self.assertRaises(ValueError):
                friend_snapshot(invalid, 'alice', 21)

    def test_pending_campus_graph_preserves_project_evidence_without_inventing_a_rank(self):
        value = snapshot()
        value['curriculum_rank'] = dict(status='pending', rank=None, track=None, section=None, project_ids=[1001], stale=False)
        self.assertEqual(friend_snapshot(value, 'alice', 21)['curriculum_rank']['status'], 'pending')
        value['curriculum_rank']['rank'] = 6
        with self.assertRaises(ValueError):
            friend_snapshot(value, 'alice', 21)

    def test_failed_attempt_rank_evidence_requires_no_ongoing_work_and_latest_failed_attempts(self):
        value = snapshot(items=[attempt(1323, status='finished', validated=False, mark=0)])
        value['curriculum_rank'] = dict(status='inferred', rank=5, track='old', section='common-core',
                                        project_ids=[1323], stale=False, source='failed_attempt')
        self.assertEqual(friend_snapshot(value, 'alice', 21)['curriculum_rank']['rank'], 5)
        for change in ('validated', 'ongoing', 'superseded', 'unknown', 'source'):
            invalid = deepcopy(value)
            if change == 'validated':
                invalid['items'][0]['validated'] = True
            elif change == 'ongoing':
                invalid['items'].append(attempt(1001, id=2))
            elif change == 'superseded':
                invalid['items'].append(attempt(1323, id=2, status='finished', validated=True, mark=100))
            elif change == 'unknown':
                invalid['items'][0]['validated'] = None
            else:
                invalid['curriculum_rank']['source'] = 'invented'
            with self.assertRaises(ValueError):
                friend_snapshot(invalid, 'alice', 21)

class FriendCoreProviderTests(unittest.TestCase):
    def test_summary_provider_validates_batch_identity_and_complete_coverage(self):
        class Api:
            def __init__(self):
                self.value = {'items': [{**snapshot(items=[]), 'details_complete': False, 'projects_loaded': False}], 'missing': ['bob']}
            def request(self, method, path, **options):
                self.call = (method, path, options)
                return self.value
        api = Api(); provider = HttpProjectProvider(api)
        values = provider.get_friend_summaries(['alice', 'bob'], 21)
        self.assertEqual(values[0]['login'], 'alice')
        self.assertEqual(api.call[1], '/v1/friends/summaries')
        from ft_tui.features.friends.adapters.storage import validated_project_count
        self.assertIsNone(validated_project_count(values[0]))
        for changed in (
            {'missing': []}, {'missing': ['bob', 'bob']}, {'missing': ['other']},
            {'items': [{**values[0], 'login': 'other'}]},
            {'items': [values[0], values[0]]},
            {'items': [{**values[0], 'details_complete': True}]},
        ):
            api.value = {'items': values, 'missing': ['bob'], **changed}
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                provider.get_friend_summaries(['alice', 'bob'], 21)

    def test_summary_view_is_explicit_and_rejects_malformed_partial_snapshots(self):
        class Api:
            def request(self, method, path, **options):
                self.call = (method, path, options)
                return {**snapshot(items=[]), 'details_complete': False, 'projects_loaded': False}
        api = Api(); provider = HttpProjectProvider(api)
        value = provider.get_friend_summary('alice', 21)
        self.assertEqual(api.call, ('GET', '/v1/friends/alice', {'params': {'cursus_id': 21, 'view': 'summary', 'include_xp': 'false'}, 'timeout': 30.0}))
        for invalid in ({'projects_loaded': 0}, {'details_complete': True}, {'details_complete': None}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                friend_snapshot({**value, **invalid}, 'alice', 21)

    def test_core_snapshot_explicitly_defers_xp_and_keeps_response_validation(self):
        class Api:
            wrong=False
            def request(self,method,path,**options):
                self.call=(method,path,options)
                return snapshot('bob' if self.wrong else 'alice')
        api=Api();provider=HttpProjectProvider(api)
        self.assertEqual(provider.get_friend_core('alice',21,refresh=True)['login'],'alice')
        self.assertEqual(api.call,('GET','/v1/friends/alice',{'params':{'cursus_id':21,'refresh':'true','include_xp':'false'},'timeout':180.0}))
        api.wrong=True
        with self.assertRaises(ValueError):provider.get_friend_core('alice',21)
