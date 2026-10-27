"""Compatibility alias for project registration and team workflows."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module('ft_tui.features.projects.registration.presentation')
