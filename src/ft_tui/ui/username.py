"""Literal username rendering with optional color gradient presets."""
from rich.style import Style
from rich.text import Text


USERNAME_GRADIENTS = {
    'off': ('Off', None),
    'ocean': ('Ocean', ((88, 201, 192), (122, 162, 247))),
    'sunset': ('Sunset', ((230, 180, 80), (247, 118, 142))),
    'aurora': ('Aurora', ((114, 214, 176), (187, 154, 247))),
}


def username_text(login: str, preset: str) -> Text:
    """Preserve literal text and interpolate RGB colors across its characters."""
    colors = USERNAME_GRADIENTS.get(preset, USERNAME_GRADIENTS['off'])[1]
    result = Text(style='bold', no_wrap=True, overflow='ellipsis')
    if colors is None:
        result.append(login)
        return result
    start, end = colors
    for index, character in enumerate(login):
        fraction = index / max(1, len(login) - 1)
        rgb = tuple(round(a + (b - a) * fraction) for a, b in zip(start, end))
        result.append(character, Style(color='#%02x%02x%02x' % rgb))
    return result
