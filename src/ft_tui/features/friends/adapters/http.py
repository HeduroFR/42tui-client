"""Existing provider capability/fallback policy; no HTTP/protocol changes."""
import httpx

class ProviderFriendsReader:
    def summary(self, provider, login, cursus, **options):
        fetch = getattr(provider,'get_friend_summary',None) or getattr(provider,'get_friend_core',None) or provider.get_friend
        try:
            return fetch(login,cursus,**options)
        except Exception as error:
            if (not callable(getattr(provider,'get_friend_summary',None)) or
                    not isinstance(error,httpx.HTTPStatusError) or error.response.status_code not in (400,404)):
                raise
            return provider.get_friend_core(login,cursus,**options)
    def detail(self, provider, login, cursus, **options):
        return provider.get_friend_core(login,cursus,**options)
    def batch(self, provider, logins, cursus):
        return provider.get_friend_summaries(logins,cursus)
    def search(self, provider, query, **options):
        return provider.search_students(query,**options)
