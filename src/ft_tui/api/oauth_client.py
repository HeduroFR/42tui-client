"""OAuth device pairing and DPoP-authenticated API client."""

import base64
import errno
import hashlib
import logging
import os
import json
import re
import stat
import secrets
import shutil
import subprocess
import sys
import time
import webbrowser
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ft_tui.infrastructure.security.keychain import CredentialStore, CredentialStoreProtocol


ACCESS_REFRESH_SKEW_SECONDS = 60
logger = logging.getLogger(__name__)


def _configured_browser_launchers() -> list[list[str]]:
    """Resolve the browser setting independently of broken URL associations."""
    settings = shutil.which("xdg-settings")
    if not settings:
        return []
    try:
        result = subprocess.run(
            [settings, "get", "default-web-browser"], capture_output=True,
            text=True, stdin=subprocess.DEVNULL, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode or not isinstance(result.stdout, str):
        return []
    desktop_id = result.stdout.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.desktop", desktop_id):
        return []
    commands = []
    gtk_launch = shutil.which("gtk-launch")
    if gtk_launch:
        commands.append([gtk_launch, desktop_id])
    gio = shutil.which("gio")
    if gio:
        home = Path.home()
        directories = [Path(os.environ.get("XDG_DATA_HOME") or home/".local/share")]
        directories.extend(Path(part) for part in
                           (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
                           if part and Path(part).is_absolute())
        directories.extend((home/".local/share/flatpak/exports/share", Path("/var/lib/flatpak/exports/share")))
        for directory in dict.fromkeys(directories):
            desktop_file = directory/"applications"/desktop_id
            if desktop_file.is_file():
                commands.append([gio, "launch", str(desktop_file)])
                break
    return commands


def open_authorization_browser(url: str) -> bool:
    """Open the desktop's default browser, then try installed Linux browsers.

    BROWSER remains an explicit user override. Pairing also exposes a manual
    link, so browser launch failure must never prevent authorization polling.
    """
    if sys.platform.startswith("linux") and not os.environ.get("BROWSER"):
        commands = _configured_browser_launchers()
        for command in (("xdg-open",), ("gio", "open")):
            executable = shutil.which(command[0])
            if executable:
                commands.append([executable, *command[1:]])
        for command in commands:
            try:
                result = subprocess.run(
                    [*command, url], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                )
                if result.returncode == 0:
                    return True
            except (OSError, subprocess.TimeoutExpired):
                continue
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            executable = shutil.which(name)
            if executable:
                try:
                    if webbrowser.Chrome(executable).open(url, new=2):
                        return True
                except (webbrowser.Error, OSError):
                    continue
        return False
    return webbrowser.open(url, new=2)


def _default_refresh_lock_directory() -> Path:
    from ft_tui.config.settings import data_dir
    return data_dir() / "credentials"


@contextmanager
def _interprocess_refresh_lock(path: Path) -> Iterator[None]:
    """Serialize per-user refreshes with an OS lock; the file stores no credentials."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = path.parent.lstat()
        if not stat.S_ISDIR(directory.st_mode) or (os.name != "nt" and (directory.st_uid != os.getuid() or directory.st_mode & 0o077)):
            raise OSError("Refresh lock directory must be private and owned by the current user")
        descriptor_flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            descriptor_flags |= os.O_NOFOLLOW
        descriptor = os.open(path, descriptor_flags, 0o600)
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
                lock_stat = os.fstat(descriptor)
                if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != os.getuid():
                    raise OSError("Refresh lock file must be a regular file owned by the current user")
            else:
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"\0")
            if os.name == "nt":
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.EACCES, errno.EPERM}:
            raise OAuthClientError("Could not securely lock OAuth credential refresh") from error
        raise OAuthClientError("Could not lock OAuth credential refresh") from error


class OAuthClientError(RuntimeError):
    """The OAuth backend returned an invalid or unusable response."""


@dataclass(frozen=True, slots=True)
class DeviceCredentials:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: str
    private_key_pem: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PairingStart:
    handle: str
    authorization_url: str
    expires_at: str
    browser_opened: bool = False


@dataclass(frozen=True, slots=True)
class PairingResult:
    status: str
    credentials: DeviceCredentials | None = None


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_response(response: Any) -> dict[str, Any]:
    import httpx

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        try:
            payload = response.json()
        except ValueError:
            raise error
        backend_error = payload.get("error") if isinstance(payload, dict) else None
        # Only stable, known API codes may enter UI logs; never log raw bodies.
        known_errors = {
            "invalid_upstream_response", "upstream_unavailable", "upstream_rate_limited",
            "upstream_budget_exhausted", "reauthorization_required", "redis_unavailable",
            "cache_busy", "cache_lease_lost", "data_service_unavailable", "invalid_query",
            "invalid_device_credentials", "session_service_unavailable",
            "invalid_project_slug", "invalid_upstream_resource", "invalid_subject_url",
            "subject_permission_denied", "subject_attachment_scan_limit_exceeded", "subject_unavailable", "subject_too_large", "invalid_subject_pdf",
            "project_scan_deadline_exceeded", "project_catalog_scan_limit_exceeded",
            "project_scan_limit_exceeded", "cursus_scan_limit_exceeded",
        }
        if isinstance(backend_error, str) and backend_error in known_errors:
            raise httpx.HTTPStatusError(
                f"{error} [42TUI error: {backend_error}]",
                request=error.request, response=error.response,
            ) from error
        raise
    payload = response.json()
    if not isinstance(payload, dict):
        raise OAuthClientError("Invalid response from the OAuth service")
    return payload


class OAuthClient:
    def __init__(
        self,
        base_url: str,
        credential_store: CredentialStoreProtocol | None = None,
        *,
        http_client: Any = None,
        browser_open: Callable[[str], Any] = open_authorization_browser,
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] | None = None,
        lock_directory: str | Path | None = None,
    ):
        parts = urlsplit(base_url)
        if not parts.netloc or not parts.hostname or parts.username or parts.password:
            raise ValueError("OAuth API base URL must be absolute and contain no user credentials")
        if parts.query or parts.fragment:
            raise ValueError("OAuth API base URL must not include a query or fragment")
        local_http = parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
        if parts.scheme != "https" and not local_http:
            raise ValueError("OAuth API base URL must use HTTPS")
        self.base_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        if not self.base_url:
            raise ValueError("OAuth API base URL is required")
        if http_client is None:
            import httpx
            http_client = httpx.Client(timeout=10.0, follow_redirects=False)
        self.session_expired = False
        self.on_session_expired: Callable[[], None] | None = None
        self.http = http_client
        self.store = credential_store if credential_store is not None else CredentialStore()
        self.browser_open = browser_open
        self.clock = clock
        self.id_factory = id_factory or (lambda: secrets.token_urlsafe(24))
        self._credentials: DeviceCredentials | None = None
        self._refresh_lock = Lock()
        self._pairing_keys: dict[str, str] = {}
        self.lock_directory = Path(lock_directory) if lock_directory is not None else _default_refresh_lock_directory()

    @property
    def credentials(self) -> DeviceCredentials | None:
        return self._load_credentials()

    def replace_credential_store(self, store: CredentialStoreProtocol) -> tuple[CredentialStoreProtocol, DeviceCredentials | None]:
        """Switch stores while excluding concurrent refreshes and clear cached credentials."""
        with self._credential_lock():
            previous = self.store, self._credentials
            self.store = store
            self._credentials = None
            return previous

    def create_pairing(self, *, theme: dict[str, str] | None = None) -> PairingStart:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        with self._credential_lock():
            self._credentials = None
            current = self._load_credentials()
            private_key = self._private_key(current.private_key_pem) if current else ec.generate_private_key(ec.SECP256R1())
            pem = private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode("ascii")
            # Save the key before sending its public half so restarts can continue polling.
            saved = (
                DeviceCredentials(current.access_token, current.refresh_token, current.expires_at, pem)
                if current
                else DeviceCredentials("", "", "", pem)
            )
            self.store.save(asdict(saved))
            self._credentials = saved
        response = self.http.request(
            "POST",
            self._url("/v1/pairings"),
            json={"installation_public_key": self._public_jwk(private_key)},
            headers={"Accept": "application/json"},
        )
        payload = _decode_response(response)
        try:
            start = PairingStart(
                str(payload["pairing_handle"]),
                str(payload["authorization_url"]),
                str(payload["expires_at"]),
            )
        except (KeyError, TypeError) as error:
            raise OAuthClientError("Invalid pairing response from OAuth service") from error
        self._validate_authorization_url(start.authorization_url, start.handle)
        self._pairing_keys[start.handle] = pem
        # Add cosmetic hints only after validating the server's original URL.
        # Older backends ignore the optional query field.
        colors = [(theme or {}).get(key, "") for key in ("background", "surface", "foreground", "primary", "success")]
        if all(isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color) for color in colors):
            palette = ",".join(color[1:].lower() for color in colors)
            start = PairingStart(start.handle, start.authorization_url + "&" + urlencode({"theme": palette}), start.expires_at)
        try:
            opened = bool(self.browser_open(start.authorization_url))
        except (webbrowser.Error, OSError):
            # Do not log the URL or browser exception: the pairing handle is private.
            logger.info("Authorization browser unavailable; use the manual pairing link")
            opened = False
        return PairingStart(start.handle, start.authorization_url, start.expires_at, opened)

    def poll_pairing(self, handle: str) -> PairingResult:
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", handle):
            raise ValueError("Invalid pairing handle")
        response = self.http.request("GET", self._url(f"/v1/pairings/{handle}"), headers={"Accept": "application/json"})
        payload = _decode_response(response)
        status = payload.get("status")
        if status != "approved":
            if status not in {"pending", "expired", "denied", "consumed"}:
                raise OAuthClientError("Invalid pairing state from OAuth service")
            if status != "pending":
                self._pairing_keys.pop(handle, None)
            return PairingResult(status)
        raw = payload.get("credentials")
        if not isinstance(raw, dict):
            raise OAuthClientError("Invalid pairing credentials from OAuth service")
        with self._credential_lock():
            self._credentials = None
            current = self._load_credentials()
            expected_key = self._pairing_keys.pop(handle, None)
            if current is None or not current.private_key_pem or (expected_key is not None and current.private_key_pem != expected_key):
                raise OAuthClientError("Installation key changed during pairing")
            credentials = DeviceCredentials(
                str(raw.get("access_token", "")),
                str(raw.get("refresh_token", "")),
                str(raw.get("expires_at", "")),
                current.private_key_pem,
            )
            if not credentials.access_token or not credentials.refresh_token or not credentials.expires_at:
                raise OAuthClientError("Incomplete pairing credentials from OAuth service")
            self._save_credentials(credentials)
        return PairingResult(status, credentials)

    def event_stream(self, stop):
        """Open SSE with fresh DPoP headers; never hold the credential lock while reading."""
        import httpx
        url = self._url('/v1/events')
        with self._credential_lock():
            credentials = self._ensure_access_credentials()
            headers = {'Authorization': f'DPoP {credentials.access_token}',
                       'DPoP': self._proof('GET', url, credentials.access_token),
                       'Accept': 'text/event-stream'}
        with self.http.stream('GET', url, headers=headers, timeout=httpx.Timeout(30, read=45)) as response:
            if response.status_code == 401:
                # A rotated token can race stream opening; only reject credentials
                # that are still current in the shared secure store.
                response.read()
                with self._credential_lock():
                    latest = self._reload_credentials()
                    if latest.access_token == credentials.access_token:
                        self._mark_session_expired(latest)
            response.raise_for_status()
            if not response.headers.get('content-type', '').startswith('text/event-stream'):
                raise OAuthClientError('Invalid event stream response')
            event, data = '', []
            for line in response.iter_lines():
                if stop.is_set():
                    break
                if not line:
                    if event in ('ready', 'changed') and data:
                        topic = '\n'.join(data)
                        if topic in ('resync', 'clubs', 'social'):
                            yield topic
                    event, data = '', []
                elif line.startswith('event:'):
                    event = line[6:].strip()
                elif line.startswith('data:'):
                    data.append(line[5:].lstrip())

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        import httpx

        kwargs.setdefault("timeout", 180.0 if path.startswith("/v1/me/") else 30.0)
        url = self._url(path)
        params = kwargs.pop("params", None)
        if params:
            query = urlencode(params, doseq=True)
            url += ("&" if "?" in url else "?") + query
        headers = dict(kwargs.pop("headers", {}))
        previous_proof_fingerprint: str | None = None
        for attempt in range(2):
            with self._credential_lock():
                credentials = self._ensure_access_credentials()
                proof = self._proof(method, url, credentials.access_token)
                proof_fingerprint = self._proof_id_fingerprint(proof)
                attempt_headers = {
                    **headers,
                    "Authorization": f"DPoP {credentials.access_token}",
                    "Accept": "application/json",
                    "DPoP": proof,
                }
            if attempt:
                logger.warning(
                    "OAuth API GET %s retrying with fresh DPoP proof id=%s previous_id=%s",
                    urlsplit(url).path,
                    proof_fingerprint,
                    previous_proof_fingerprint or "unknown",
                )
            try:
                # HTTP reads may be slow; credential rotation remains serialized.
                return _decode_response(self.http.request(method, url, headers=attempt_headers, **kwargs))
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 401:
                    try:
                        code = error.response.json().get("error")
                    except (ValueError, AttributeError):
                        code = None
                    if code == "reauthorization_required" or (
                        code == "invalid_device_credentials" and (attempt or method.upper() != "GET")
                    ):
                        with self._credential_lock():
                            latest = self.store.load()
                            # Ignore rejection of a session replaced during this request.
                            if latest and latest.get("access_token") == credentials.access_token:
                                self._mark_session_expired(self._require_credentials())
                if attempt:
                    if method.upper() == "GET" and error.response.status_code == 401:
                        logger.warning(
                            "OAuth API GET %s retry failed with HTTP 401 proof_id=%s",
                            urlsplit(url).path,
                            proof_fingerprint,
                        )
                    raise
                if method.upper() != "GET" or error.response.status_code != 401:
                    raise
                try:
                    payload = error.response.json()
                except ValueError:
                    raise error
                if not isinstance(payload, dict) or payload.get("error") != "invalid_device_credentials":
                    logger.warning("OAuth API GET %s returned a non-retryable 401 body", urlsplit(url).path)
                    raise error
                previous_proof_fingerprint = proof_fingerprint
                # Retry safe reads once with current credentials and a fresh proof.
        raise OAuthClientError("Protected API request did not complete")

    def list_cursuses(self) -> dict[str, Any]:
        """Forward the authenticated cursus request through the DPoP client."""
        return self.request("GET", "/v1/cursuses")

    def refresh(self) -> DeviceCredentials:
        with self._credential_lock():
            self._reload_credentials()
            return self._refresh_unlocked()

    def _refresh_unlocked(self) -> DeviceCredentials:
        credentials = self._require_credentials()
        url = self._url("/v1/sessions/refresh")
        response = self.http.request(
            "POST",
            url,
            json={"refresh_token": credentials.refresh_token},
            headers={"DPoP": self._proof("POST", url, credentials.refresh_token), "Accept": "application/json"},
        )
        import httpx

        try:
            payload = _decode_response(response)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 401:
                self._mark_session_expired(credentials)
            raise
        refreshed = DeviceCredentials(
            str(payload.get("access_token", "")),
            str(payload.get("refresh_token", "")),
            str(payload.get("expires_at", "")),
            credentials.private_key_pem,
        )
        if not refreshed.access_token or not refreshed.refresh_token or not refreshed.expires_at:
            raise OAuthClientError("Incomplete refreshed credentials from OAuth service")
        self._save_credentials(refreshed)
        return refreshed

    def disconnect(self) -> None:
        with self._credential_lock():
            credentials = self._ensure_access_credentials()
            url = self._url("/v1/sessions/current")
            proof = self._proof("DELETE", url, credentials.access_token)
            response = self.http.request(
                "DELETE",
                url,
                headers={"Authorization": f"DPoP {credentials.access_token}", "DPoP": proof, "Accept": "application/json"},
            )
            response.raise_for_status()
            self.store.delete()
            self._credentials = None

    def close(self) -> None:
        close = getattr(self.http, "close", None)
        if close:
            close()

    def _validate_authorization_url(self, authorization_url: str, expected_handle: str) -> None:
        try:
            auth = urlsplit(authorization_url)
            auth_port = auth.port
            query = parse_qsl(auth.query, keep_blank_values=True, strict_parsing=True)
        except ValueError as error:
            raise OAuthClientError("OAuth service returned an unsafe authorization URL") from error
        if (
            not auth.netloc
            or not auth.hostname
            or auth.username
            or auth.password
            or auth.fragment
            or auth.path != "/oauth/42/start"
            or len(query) != 1
            or query[0][0] != "pairing"
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", query[0][1])
            or query[0][1] != expected_handle
        ):
            raise OAuthClientError("OAuth service returned an unsafe authorization URL")

        base = urlsplit(self.base_url)
        try:
            base_port = base.port
            auth_effective_port = auth_port if auth_port is not None else (443 if auth.scheme == "https" else 80)
            base_effective_port = base_port if base_port is not None else (443 if base.scheme == "https" else 80)
            auth_origin = (auth.scheme, auth.hostname, auth_effective_port)
            base_origin = (base.scheme, base.hostname, base_effective_port)
        except ValueError as error:
            raise OAuthClientError("OAuth service returned an unsafe authorization URL") from error
        if auth_origin != base_origin:
            raise OAuthClientError("OAuth service returned an unsafe authorization URL")
        if auth.scheme == "http" and auth.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise OAuthClientError("OAuth service returned an unsafe authorization URL")
        if auth.scheme not in {"http", "https"}:
            raise OAuthClientError("OAuth service returned an unsafe authorization URL")

    def _ensure_access_credentials(self) -> DeviceCredentials:
        # Callers hold _credential_lock while preparing credentials and DPoP proofs.
        credentials = self._reload_credentials()
        if self._expires_soon(credentials):
            return self._refresh_unlocked()
        return credentials

    @contextmanager
    def _credential_lock(self) -> Iterator[None]:
        with self._refresh_lock:
            with _interprocess_refresh_lock(self._refresh_lock_path()):
                yield

    def _refresh_lock_path(self) -> Path:
        return self.lock_directory / "session.lock"

    def _reload_credentials(self) -> DeviceCredentials:
        # The credential store is the shared source of truth across client instances.
        self._credentials = None
        return self._require_credentials()

    def _expires_soon(self, credentials: DeviceCredentials) -> bool:
        try:
            expires_at = datetime.fromisoformat(credentials.expires_at.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError) as error:
            raise OAuthClientError("Stored device credential expiry is invalid") from error
        if expires_at.tzinfo is None:
            raise OAuthClientError("Stored device credential expiry must include a timezone")
        refresh_after = datetime.fromtimestamp(self.clock() + ACCESS_REFRESH_SKEW_SECONDS, timezone.utc)
        return expires_at <= refresh_after

    def _load_credentials(self) -> DeviceCredentials | None:
        if self._credentials is not None:
            return self._credentials
        data = self.store.load()
        if data is None:
            return None
        try:
            self._credentials = DeviceCredentials(**data)
        except (TypeError, ValueError) as error:
            raise OAuthClientError("Stored device credentials are invalid") from error
        return self._credentials

    def _mark_session_expired(self, credentials: DeviceCredentials) -> None:
        # Pairing may finish while an older HTTP request is still in flight.
        if self._credentials is credentials and not self.session_expired:
            self.session_expired = True
            if self.on_session_expired is not None:
                self.on_session_expired()

    def _save_credentials(self, credentials: DeviceCredentials) -> None:
        self.store.save(asdict(credentials))
        self._credentials = credentials
        self.session_expired = False

    def _require_credentials(self) -> DeviceCredentials:
        credentials = self._load_credentials()
        if (
            credentials is None
            or not credentials.access_token
            or not credentials.refresh_token
            or not credentials.private_key_pem
        ):
            raise OAuthClientError("42TUI is not connected to a 42 account")
        return credentials

    def _url(self, path: str) -> str:
        return self.base_url + "/" + path.lstrip("/")

    def _private_key(self, pem: str):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
            raise OAuthClientError("Stored installation key is not a P-256 key")
        return key

    def _public_jwk(self, private_key: Any) -> dict[str, str]:
        numbers = private_key.public_key().public_numbers()
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": _b64url(numbers.x.to_bytes(32, "big")),
            "y": _b64url(numbers.y.to_bytes(32, "big")),
        }

    def _proof(self, method: str, uri: str, token: str) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        credentials = self._require_credentials()
        private_key = self._private_key(credentials.private_key_pem)
        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": self._public_jwk(private_key)}
        claims = {
            "htm": method.upper(),
            "htu": uri,
            "iat": int(self.clock()),
            "jti": self.id_factory(),
            "ath": _b64url(hashlib.sha256(token.encode("ascii")).digest()),
        }
        encoded_header = _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
        encoded_claims = _b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
        message = f"{encoded_header}.{encoded_claims}"
        der = private_key.sign(message.encode("ascii"), ec.ECDSA(hashes.SHA256()))
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        r, s = decode_dss_signature(der)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return f"{message}.{_b64url(signature)}"

    @staticmethod
    def _proof_id_fingerprint(proof: str) -> str:
        try:
            claims_part = proof.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(claims_part + "=" * (-len(claims_part) % 4)))
            jti = claims.get("jti") if isinstance(claims, dict) else None
        except (IndexError, ValueError, TypeError):
            return "unknown"
        if not isinstance(jti, str):
            return "unknown"
        return hashlib.sha256(jti.encode("utf-8")).hexdigest()[:12]

    def _new_private_key_pem(self) -> str:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        return key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
