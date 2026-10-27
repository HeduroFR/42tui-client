"""Read account sources independently without UI or persistence side effects."""
import logging
from .ports import AccountReader

logger = logging.getLogger(__name__)


class AccountService:
    def read(self, provider: AccountReader) -> tuple[dict | None, list | None]:
        profile = None
        try:
            get_profile = getattr(provider, 'get_profile', None)
            if callable(get_profile):
                profile = get_profile()
        except Exception as error:
            logger.warning('OAuth API profile request failed (%s): %s', type(error).__name__, error)
        cursuses = None
        try:
            cursuses = provider.list_cursuses()
        except Exception as error:
            logger.warning('OAuth API cursus request failed (%s): %s', type(error).__name__, error)
        return profile, cursuses
