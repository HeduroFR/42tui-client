"""Immutable reference geometry, independent of changing machine observations."""
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json


@lru_cache(maxsize=4)
def load_layout(view: str) -> tuple[tuple[str | None, ...], ...]:
    data = json.loads(files('ft_tui.features.cluster_map').joinpath('layout.json').read_text())
    if view not in ('all', 'c1', 'c2', 'c3'):
        raise ValueError('Invalid cluster view')
    matrix = data['campus'] if view == 'all' else data['clusters'][int(view[1])-1]
    return tuple(tuple(None if host == '.' else host for host in row) for row in matrix)


def positions(view: str) -> dict[str, tuple[int, int]]:
    return {host: (x, y) for y, row in enumerate(load_layout(view))
            for x, host in enumerate(row) if host is not None}


@dataclass(frozen=True)
class TileSize:
    width: int
    height: int
    mode: str


def fit_tiles(view: str, width: int, height: int) -> TileSize | None:
    matrix = load_layout(view)
    w, h = width // len(matrix[0]), height // len(matrix)
    if view!='all':
        aisles=sum(not any(row) for row in matrix)
        h=(height-aisles)//(len(matrix)-aisles)
        # Keep the whole seat taller than it is wide in typical 1:2 cells,
        # while reserving enough columns for an eight-character login.
        w=min(w,max(9,round(h*1.5)))
    if w < 2 or h < 1:
        return None
    # Odd widths give single-cell status icons an exact horizontal center.
    # Retain the two-column fallback in very narrow terminals; never trim height.
    if w>2 and w%2==0:w-=1
    return TileSize(w, h, 'portrait' if w >= 4 and h >= 3 else 'symbol')


def neighbor(view: str, hostname: str, direction: str) -> str | None:
    points = positions(view)
    if hostname not in points or direction not in ('left', 'right', 'up', 'down'):
        return None
    x, y = points[hostname]
    horizontal = direction in ('left', 'right')
    sign = -1 if direction in ('left', 'up') else 1
    candidates = [(abs(px-x) + abs(py-y), host) for host, (px, py) in points.items()
                  if (py == y and (px-x)*sign > 0 if horizontal else px == x and (py-y)*sign > 0)]
    return min(candidates)[1] if candidates else None


def row_heights(view: str, size: TileSize) -> tuple[int, ...]:
    """Only empty aisle rows collapse; workstation coordinates stay ordered."""
    return tuple(1 if view!='all' and not any(row) else size.height for row in load_layout(view))
