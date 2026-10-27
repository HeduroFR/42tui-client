import unittest
from copy import deepcopy
from ft_tui.api.friends_types import friend_directory_page
from ft_tui.api.http_client import HttpProjectProvider
from tests.friends_fixtures import directory_page


class FriendDirectoryTests(unittest.TestCase):
    def test_provider_pagination_and_projected_identity_validation(self):
        class API:
            def request(self, method, path, **kwargs):
                self.call = (method, path, kwargs)
                return directory_page([{'user_id': '50', 'login': 'alice', 'display_name': 'Alice'}])
        api = API()
        self.assertEqual(HttpProjectProvider(api).list_friend_directory_page(31)['items'][0]['login'], 'alice')
        self.assertEqual(api.call, ('GET', '/v1/friends/directory/users', {'params': {'campus_id': 31, 'page': 1}}))
        for campus, page in [(True, 1), (0, 1), (31, 0), (31, 101)]:
            with self.assertRaises(ValueError):
                HttpProjectProvider(api).list_friend_directory_page(campus, page)

    def test_rejects_scope_duplicates_and_false_pagination_claims(self):
        data = directory_page([{'user_id': '50', 'login': 'alice', 'display_name': 'Alice'}])
        for mutate in [lambda x: x.update(campus_id=32), lambda x: x.update(page=2),
                       lambda x: x['items'].append(deepcopy(x['items'][0])),
                       lambda x: x.update(next_page=None), lambda x: x.update(truncated=True),
                       lambda x: x['items'][0].update(user_id='0'),
                       lambda x: x['meta'].update(cached_at='bad')]:
            value = deepcopy(data); mutate(value)
            with self.assertRaises(ValueError):
                friend_directory_page(value, 31, 1)
        full = [{'user_id': str(i + 1), 'login': f'user{i}', 'display_name': 'User'} for i in range(100)]
        self.assertEqual(friend_directory_page(directory_page(full), 31, 1)['next_page'], 2)
        last = friend_directory_page(directory_page(full, page=100), 31, 100)
        self.assertTrue(last['truncated']); self.assertIsNone(last['next_page'])
