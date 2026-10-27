"""The read core is headless; shell integration owns scope and persistence."""
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import contextmanager
from ft_tui.app.read_cache import account_context, account_scope, app_cache


class ReadContextTests(unittest.TestCase):
    def make_app(self):
        return SimpleNamespace(provider=SimpleNamespace(api=SimpleNamespace(base_url='https://example.test/api')),
                               oauth_client=None, account_id='42', account_generation=0)

    def test_read_core_imports_without_ui_database_or_http_dependencies(self):
        source = Path(__file__).resolve().parents[1]/'src'
        command = f"import sys; sys.path.insert(0, {str(source)!r}); from ft_tui.shared.read_cache import ReadCache; assert not any(x in sys.modules for x in ('textual','sqlalchemy','httpx'))"
        result = subprocess.run([sys.executable, '-S', '-c', command], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_context_preserves_tuple_keys_and_switch_clears_entries_and_revocations(self):
        app = self.make_app()
        old = account_scope(app)
        self.assertEqual(account_context(app).key, old)
        cache = app_cache(app)
        cache.revoked[old] = RuntimeError('revoked')
        app.account_generation += 1
        self.assertIs(app_cache(app), cache)
        self.assertEqual(cache.entries, {})
        self.assertEqual(cache.revoked, {})
        self.assertNotEqual(account_scope(app), old)

    def test_authorization_callback_ignores_old_context_and_persists_current_scope(self):
        app = self.make_app()
        @contextmanager
        def factory(): yield 'session'
        app.session_factory = factory
        notifications = []
        app._read_authorization_lost = notifications.append
        cache = app_cache(app)
        old = account_scope(app)
        with patch('ft_tui.features.friends.adapters.storage.forget_authorization') as forget:
            app.account_generation += 1
            cache.on_authorization_lost(old)
            forget.assert_not_called()
            current = account_scope(app)
            cache.on_authorization_lost(current)
            forget.assert_called_once_with('session', '42', origin='https://example.test/api')
            self.assertEqual(notifications, [current])

    def test_app_cache_uses_shared_cache_and_normalized_origin(self):
        from ft_tui.app import read_cache
        app = self.make_app()
        with patch('ft_tui.app.read_cache.ReadCache') as factory:
            self.assertIs(read_cache.app_cache(app), factory.return_value)
            factory.assert_called_once_with()
        with patch('ft_tui.app.read_cache.backend_origin', return_value='https://patched.test'):
            self.assertEqual(read_cache.account_scope(app)[0], 'https://patched.test')

    def test_portrait_limit_has_one_non_ui_policy_owner(self):
        from ft_tui.shared.portraits import MAX_PORTRAIT_BYTES
        from ft_tui.features.cluster_map.views.portrait import MAX_PORTRAIT_BYTES as view_limit
        self.assertEqual(MAX_PORTRAIT_BYTES, 512*1024)
        self.assertEqual(MAX_PORTRAIT_BYTES, view_limit)
