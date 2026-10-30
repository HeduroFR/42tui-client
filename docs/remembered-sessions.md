# Remembered account sessions

42TUI can keep a session only until the app exits, use the OS keyring, or save
an encrypted session protected by a separate 42TUI passphrase. Choose a long,
unique passphrase; do not use your 42 password. The encrypted file contains the
access and refresh tokens and the device private key. The passphrase is not saved.

Choose **Remember with a passphrase** when connecting. On later launches, unlock
the saved session with the same passphrase. Cancel to leave it locked; after
onboarding, connect or unlock a session to enter the app. A session
only connection pairs again after restarting. From a connected keyring session,
**Move keyring session to passphrase** explicitly migrates it; 42TUI checks the
new vault before removing the old keyring entry. If migration reports an error,
check both stores before retrying; a vault may have been created.

A forgotten passphrase cannot be recovered. Choose **Discard saved session** and
confirm to remove the local vault, then connect again. This does not delete local
projects and does not revoke the old server session. Disconnect while an unlocked
session is online to revoke it. If revocation fails, the local vault is retained.

A copied vault allows offline passphrase guessing; shared campus home directories
may make it accessible from other machines. Encryption protects saved credentials,
not an unlocked application or a compromised workstation. It does not encrypt
project data, and Python cannot guarantee secure erasure of secrets from memory.
