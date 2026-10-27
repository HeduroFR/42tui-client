"""Cached, bundled WIP pixel frames; no artwork generation or I/O per tick."""
from functools import lru_cache
from importlib.resources import files

from PIL import Image


POSES = ('idle', 'blink', 'crawl', 'sleep', 'settle', 'wake', 'hang', 'climb')
FRAME_SIZE = (48, 32)
FRAME_COUNT = 4


@lru_cache(maxsize=1)
def _sheet():
    with files('ft_tui').joinpath('assets/wip.png').open('rb') as stream:
        with Image.open(stream) as image:
            result = image.convert('RGBA')
    if result.size != (FRAME_SIZE[0] * FRAME_COUNT, FRAME_SIZE[1] * len(POSES)):
        raise ValueError('Invalid WIP sprite dimensions')
    return result


@lru_cache(maxsize=32)
def frame(pose: str, index: int = 0) -> Image.Image:
    """Return an immutable-by-convention frame; callers must not mutate it."""
    column = index % FRAME_COUNT
    row = POSES.index(pose)
    width, height = FRAME_SIZE
    return _sheet().crop((column * width, row * height, (column + 1) * width, (row + 1) * height))
