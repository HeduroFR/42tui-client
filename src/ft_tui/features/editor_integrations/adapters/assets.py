"""Resolve editor integration files shipped inside the package."""

from importlib import resources
from pathlib import Path

from ft_tui.integrations import INTEGRATION_VERSION


class PackagedAssets:
    """Read-only access to the packaged integration assets."""

    def version(self, editor: str) -> str:
        return INTEGRATION_VERSION

    def path(self, editor: str) -> Path:
        return Path(str(resources.files("ft_tui.integrations").joinpath("assets", editor)))
