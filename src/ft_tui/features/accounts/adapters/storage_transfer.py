"""Move an active session between credential stores under the session lock."""
from ft_tui.infrastructure.security.keychain import CredentialStore, SessionCredentialStore, SecureStoreError
from ft_tui.infrastructure.security.session_vault import SessionVault, session_vault_path


def storage_kind(store):
    if isinstance(store, CredentialStore):
        return 'keyring'
    if isinstance(store, SessionVault):
        return 'vault'
    if isinstance(store, SessionCredentialStore):
        return 'session'
    return None


def move_session(client, kind, passphrase=None, expected_source=None):
    with client._credential_lock():
        source = client.store
        if expected_source is not None and source is not expected_source:
            raise SecureStoreError('Session storage changed; retry')
        if storage_kind(source) == kind:
            return
        credentials = source.load()
        if not credentials:
            raise SecureStoreError('The current session is unavailable')
        vault_path = session_vault_path()
        if storage_kind(source) != 'vault' and kind != 'vault' and (vault_path.exists() or vault_path.is_symlink()):
            raise SecureStoreError('Another saved session exists')
        if storage_kind(source) == 'vault' and kind == 'session' and CredentialStore().load() is not None:
            raise SecureStoreError('Another saved session exists')
        if kind == 'keyring':
            target = CredentialStore()
            if target.load() is not None:
                raise SecureStoreError('The destination already contains a session')
        elif kind == 'vault':
            target = SessionVault.create(vault_path, passphrase)
        elif kind == 'session':
            target = SessionCredentialStore()
        else:
            raise SecureStoreError('Unknown session storage')
        target.save(credentials)
        if target.load() != credentials:
            raise SecureStoreError('The destination could not be verified')
        source.delete()
        client.store = target
        client._credentials = None
