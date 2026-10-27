"""Compatibility alias for the public campus-directory validator."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module('ft_tui.features.accounts.campuses')
