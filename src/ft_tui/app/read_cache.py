"""Bind reusable read coordination to shell context and persistence callbacks."""
from ft_tui.shared.context import AccountContext, normalize_origin
from ft_tui.shared.read_cache import Entry, ReadCache, ReadDeferred, ReadInvalidated


def backend_origin(app):
    api = getattr(getattr(app, 'provider', None), 'api', None) or getattr(app, 'oauth_client', None)
    return normalize_origin(getattr(api, 'base_url', ''))


def account_context(app) -> AccountContext:
    return AccountContext(backend_origin(app), getattr(app, 'account_id', None),
                          getattr(app, 'account_generation', 0), id(getattr(app, 'provider', None)))


def account_scope(app):
    """Keep the existing tuple key format at the presentation integration boundary."""
    return account_context(app).key


def app_cache(app):
    scope = account_scope(app)
    cache = getattr(app, '_read_cache', None)
    if cache is None:
        cache = app._read_cache = ReadCache()
        def authorization_lost(scope):
            if scope != account_scope(app):
                return
            factory = getattr(app, 'session_factory', None)
            if factory is not None:
                from ft_tui.features.friends.adapters.storage import forget_authorization
                with factory() as session:
                    forget_authorization(session, scope[1], origin=scope[0])
            notify = getattr(app, '_read_authorization_lost', None)
            if callable(notify):
                notify(scope)
        cache.on_authorization_lost = authorization_lost
    if getattr(app, '_read_cache_scope', None) != scope:
        cache.clear()
        cache.revoked.clear()
        app._read_cache_scope = scope
    return cache

__all__ = ["normalize_origin", "Entry", "ReadCache", "ReadDeferred", "ReadInvalidated",
           "account_context", "account_scope", "app_cache", "backend_origin"]
