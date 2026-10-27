"""Catalog navigation/loading state owned by the catalog feature."""
from dataclasses import dataclass, field


@dataclass
class CatalogState:
    status: str = 'Saved catalog'
    next_pages: list = field(default_factory=list)
    branch_cursor: str | None = None
    branch_items: list = field(default_factory=list)
    generation: int = 0
    snapshot: str | None = None
    branch_snapshot: str | None = None
    request: tuple | None = None
