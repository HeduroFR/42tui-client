"""Read account sources independently without UI or persistence side effects."""
from concurrent.futures import ThreadPoolExecutor
import logging
from .ports import AccountReader

logger = logging.getLogger(__name__)


class AccountService:
    def read(self, provider: AccountReader) -> tuple[dict | None, list | None]:
        def read_source(label, operation):
            if not callable(operation):
                return None
            try:
                return operation()
            except Exception as error:
                logger.warning('OAuth API %s request failed (%s): %s', label, type(error).__name__, error)
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            profile = pool.submit(read_source, 'profile', getattr(provider, 'get_profile', None))
            cursuses = pool.submit(read_source, 'cursus', getattr(provider, 'list_cursuses', None))
            return profile.result(), cursuses.result()
