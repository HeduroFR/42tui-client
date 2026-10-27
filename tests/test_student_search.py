import unittest
from copy import deepcopy
from ft_tui.features.friends.models import student_search_result, friend_snapshot
from ft_tui.api.http_client import HttpProjectProvider
from tests.friends_fixtures import snapshot


class StudentSearchTests(unittest.TestCase):
    def result(self):
        return {'items': [{'user_id': '50', 'login': 'alice', 'display_name': 'Alice'}],
                'index': {'status': 'building', 'count': 1, 'updated_at': None, 'stale': True}}

    def test_provider_uses_bounded_database_search(self):
        result = self.result()
        class API:
            def request(self, method, path, **kwargs):
                self.call = (method, path, kwargs)
                return result
        api = API(); provider = HttpProjectProvider(api)
        self.assertEqual(provider.search_students('ailce', exclude_ids=('42',)), result)
        self.assertEqual(api.call, ('GET', '/v1/users/search', {'params': {'q': 'ailce', 'limit': 20, 'exclude_ids': '42'}}))
        for query, limit, ids in [('a', 20, ()), ('___', 20, ()), ('alice', 21, ()), ('alice', True, ()), ('alice', 20, ('0',))]:
            with self.assertRaises(ValueError):
                provider.search_students(query, limit=limit, exclude_ids=ids)

    def test_response_rejects_duplicate_identities_unbounded_results_and_bad_metadata(self):
        for mutate in [lambda x: x['items'].append(deepcopy(x['items'][0])),
                       lambda x: x['items'][0].update(user_id='0'),
                       lambda x: x['index'].update(count=True),
                       lambda x: x['index'].update(status='complete'),
                       lambda x: x['index'].pop('updated_at'),
                       lambda x: x['index'].update(updated_at='2026-01-01T00:00:00')]:
            result = self.result(); mutate(result)
            with self.assertRaises(ValueError):
                student_search_result(result)
        with self.assertRaises(ValueError):
            student_search_result(self.result(), 0)

    def test_selected_identity_allows_canonical_rename_and_checks_id(self):
        result = snapshot('alice-new', user_id='50')
        self.assertEqual(friend_snapshot(result, 'alice', 21, user_id='50')['login'], 'alice-new')
        for expected in ('99', None):
            with self.assertRaises(ValueError):
                friend_snapshot(result, 'alice', 21, user_id=expected)
        class API:
            def request(self, method, path, **kwargs):
                self.call = (method, path, kwargs)
                return result
        api = API()
        self.assertEqual(HttpProjectProvider(api).get_friend('alice', 21, user_id='50')['login'], 'alice-new')
        self.assertEqual(api.call[2]['params'], {'cursus_id': 21, 'user_id': '50'})

    def test_legacy_logins_survive_search_snapshot_and_url_encoding(self):
        from urllib.parse import quote
        from ft_tui.features.friends.models import LOGIN
        for login in ('_Legacy42', 'UpperCase', 'Étudiant', 'a/b', 'A?B#C%', ' user '):
            with self.subTest(login=login):
                result = self.result(); result['items'][0]['login'] = login
                self.assertEqual(student_search_result(result)['items'][0]['login'], login)
                value = snapshot(login, user_id='50')
                class API:
                    def request(self, method, path, **kwargs):
                        self.call = (method, path, kwargs)
                        return value
                api = API()
                self.assertEqual(HttpProjectProvider(api).get_friend(login, 21, user_id='50')['login'], login)
                self.assertEqual(api.call[1], '/v1/friends/' + quote(login, safe=''))
        for login in ('', '   ', '.', '..', 'a\nb', 'a\x00b', 'a\x85b', 'x' * 101):
            self.assertIsNone(LOGIN.fullmatch(login))
