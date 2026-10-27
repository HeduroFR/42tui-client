"""Friend validation and operations independent of Textual and SQL sessions."""
import asyncio
from .models import friend_snapshot, student_search_result
from .ports import FriendsRepository, FriendsReader

class FriendsService:
    def __init__(self, repository: FriendsRepository, reader: FriendsReader):
        self.repository = repository
        self.reader = reader

    def configured_cursus(self, selector=None):
        return self.repository.configured_cursus(selector)
    def memberships(self, account, *, origin=''):
        return self.repository.memberships(account,origin=origin)
    def cached(self, account, cursus, *, origin=''):
        return self.repository.cached(account,cursus,origin=origin)
    def save(self, account, value, *, origin='', current=lambda:True):
        if not current():
            return False
        self.repository.save(account,value,origin=origin)
        return True
    def forget(self, account, cursus, login, *, origin=''):
        self.repository.forget(account,cursus,login,origin=origin)

    @staticmethod
    def validate(value, login, cursus, *, expected_user_id=None, owner_login=None, account_id=None):
        value = friend_snapshot(value,login,cursus,user_id=expected_user_id)
        if login == owner_login and value['user_id'] != account_id:
            raise ValueError('Account identity mismatch')
        return value

    async def summary(self, provider, login, cursus, *, refresh=False, expected_user_id=None,
                      owner_login=None, account_id=None):
        options = {'refresh':refresh}
        if expected_user_id is not None:
            options['user_id'] = expected_user_id
        value = await asyncio.to_thread(self.reader.summary,provider,login,cursus,**options)
        return self.validate(value,login,cursus,expected_user_id=expected_user_id,owner_login=owner_login,account_id=account_id)

    async def detail(self, provider, login, cursus, *, refresh=False, owner_login=None, account_id=None):
        value = await asyncio.to_thread(self.reader.detail,provider,login,cursus,refresh=refresh)
        return self.validate(value,login,cursus,owner_login=owner_login,account_id=account_id)

    async def batch(self, provider, logins, cursus, *, owner_login=None, account_id=None):
        values = await asyncio.to_thread(self.reader.batch,provider,logins,cursus)
        for value in values:
            self.validate(value,value['login'],cursus,owner_login=owner_login,account_id=account_id)
        return values

    async def search(self, provider, query, *, limit=20, exclude_ids=()):
        result = await asyncio.to_thread(self.reader.search,provider,query,limit=limit,exclude_ids=exclude_ids)
        return student_search_result(result)
