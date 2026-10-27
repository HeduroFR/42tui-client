"""Account shell storage and concrete transport composition."""
import json
from ft_tui.features.settings.adapters.storage import get_setting, save_settings
from ft_tui.features.accounts.cursus import is_main_cursus, select_default_cursus
from ft_tui.features.catalog.adapters.cursuses import sync_cursuses


def supports_session_check(client):
    from ft_tui.api.oauth_client import OAuthClient
    return isinstance(client, OAuthClient)


def connected_provider(client):
    from ft_tui.api.http_client import HttpProjectProvider
    return HttpProjectProvider(oauth_client=client)


class SqliteAccountShellRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def configured_cursus(self, session=None):
        if session is None:
            with self.session_factory() as owned:
                return self.configured_cursus(owned)
        value = get_setting(session, 'default_cursus_id')
        try:
            parsed = int(value) if value else None
        except ValueError:
            return None
        return parsed if parsed and parsed > 0 else None

    def select_default(self, cursuses, today):
        with self.session_factory() as session:
            saved_value = get_setting(session, 'default_cursus_id')
            if saved_value:
                try:
                    saved_id = int(saved_value)
                except ValueError:
                    return None, False
                saved_cursus = next((cursus for cursus in cursuses if cursus.id == saved_id), None)
                if (get_setting(session, 'default_cursus_source') == 'manual' or saved_cursus is None
                        or 'piscine' not in saved_cursus.name.casefold()):
                    return saved_id, False
                selected = select_default_cursus(cursuses, today)
                if selected is None or not is_main_cursus(selected):
                    return saved_id, False
            else:
                selected = select_default_cursus(cursuses, today)
            if selected is None:
                return None, False
            save_settings(session, {'default_cursus_id': str(selected.id), 'default_cursus_source': 'auto'})
        return selected.id, True

    def remember_account(self, account, campuses):
        with self.session_factory() as session:
            save_settings(session, {'catalog_last_account': account, 'catalog_last_campuses': json.dumps(campuses)})

    def save_cursuses(self, values):
        with self.session_factory() as session:
            sync_cursuses(session, values)

    def save_campuses(self, values):
        with self.session_factory() as session:
            save_settings(session, {'campus_directory': json.dumps(values)})
