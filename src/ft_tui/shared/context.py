"""Immutable identity values shared by feature operations and read coordination."""
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


def normalize_origin(value):
    """Include a backend path prefix, but never credentials, query or fragment."""
    if not value:
        return ''
    parts = urlsplit(str(value))
    host = (parts.hostname or '').lower()
    if ':' in host:
        host = f'[{host}]'
    port = parts.port
    if port and (parts.scheme.lower(), port) not in {('https', 443), ('http', 80)}:
        host += f':{port}'
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip('/'), '', ''))


@dataclass(frozen=True, slots=True)
class AccountContext:
    origin: str
    account_id: str | None
    generation: int
    provider_id: int

    def __post_init__(self):
        object.__setattr__(self, 'origin', normalize_origin(self.origin))

    @property
    def key(self) -> tuple[str, str | None, int, int]:
        return self.origin, self.account_id, self.generation, self.provider_id
