"""Compatibility alias preserving legacy read-cache lookup and patch behavior."""
from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module('ft_tui.app.read_cache')
