"""Composable stylesheets for the Textual application."""

from .base import BASE_CSS
from .dashboard import DASHBOARD_CSS
from .projects import PROJECTS_CSS
from .dev_log import DEV_LOG_CSS
from .settings import SETTINGS_CSS
from .friends import FRIENDS_CSS
from .cluster_map import CLUSTER_MAP_CSS

APP_CSS = "\n".join((BASE_CSS, DASHBOARD_CSS, PROJECTS_CSS, FRIENDS_CSS, DEV_LOG_CSS, CLUSTER_MAP_CSS, SETTINGS_CSS))

__all__ = ["APP_CSS"]
