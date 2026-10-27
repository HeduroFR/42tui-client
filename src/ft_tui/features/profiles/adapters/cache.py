"""Last-known dashboard state; profile restoration is bound to device credentials."""
import json
from copy import deepcopy
from hashlib import sha256

from ft_tui.api.oauth_client import DeviceCredentials
from ft_tui.features.catalog.preferences import preference_key
from ft_tui.features.settings.adapters.storage import get_setting, save_settings

PROFILE_KEY = 'dashboard_profile_snapshot'
PROFILE_FIELDS = ('account_id', 'login', 'first_name', 'last_name', 'wallet',
                  'correction_point', 'location', 'cursus_users', 'campuses')


def credential_scope(client):
    """Store only a digest, never tokens or private keys, in the dashboard cache."""
    if client is None or getattr(client, 'session_expired', False):
        return None
    try:
        credentials = client.credentials
        base_url = client.base_url
    except Exception:
        return None
    if (not isinstance(credentials, DeviceCredentials) or not isinstance(base_url, str)
            or not credentials.access_token or not credentials.refresh_token):
        return None
    return sha256(json.dumps([base_url, credentials.access_token, credentials.refresh_token,
                              credentials.private_key_pem]).encode()).hexdigest()


def valid_profile(profile):
    return (isinstance(profile, dict) and isinstance(profile.get('account_id'), str)
            and profile['account_id'].isdigit() and isinstance(profile.get('login'), str)
            and bool(profile['login']) and isinstance(profile.get('campuses', []), list)
            and all(isinstance(campus, dict) and type(campus.get('id')) is int and campus['id'] > 0
                    for campus in profile.get('campuses', [])))


def save_profile(session, client, profile):
    scope = credential_scope(client)
    if not scope or not valid_profile(profile):
        return
    clean = {key: profile[key] for key in PROFILE_FIELDS if key in profile}
    save_settings(session, {PROFILE_KEY: json.dumps({'version': 1, 'credentials': scope, 'profile': clean})})


def load_profile(session, client):
    scope = credential_scope(client)
    if not scope:
        return {}
    try:
        saved = json.loads(get_setting(session, PROFILE_KEY))
        profile = saved.get('profile')
        if saved.get('version') == 1 and saved.get('credentials') == scope and valid_profile(profile):
            return deepcopy(profile)
    except (ValueError, TypeError, AttributeError):
        pass
    return {}


def save_goals(session, account, cursus, value):
    if not account or not cursus or value.get('status') not in {'available', 'not_applicable'}:
        return
    key = preference_key(account, cursus, None, 'dashboard_goals')
    save_settings(session, {key: json.dumps(value)})


def load_goals(session, account, cursus):
    if not account or not cursus:
        return {}
    try:
        value = json.loads(get_setting(session, preference_key(account, cursus, None, 'dashboard_goals')))
        if isinstance(value, dict) and value.get('status') in {'available', 'not_applicable'}:
            return {**value, 'stale': True}
    except (ValueError, TypeError):
        pass
    return {}
