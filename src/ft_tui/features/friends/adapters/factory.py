"""Default friends composition for standalone views and production bootstrap."""
from ..service import FriendsService
from .sqlite import SqliteFriendsRepository
from .http import ProviderFriendsReader

def create_friends_service(session_factory):
    return FriendsService(SqliteFriendsRepository(session_factory),ProviderFriendsReader())
