"""Backward-compat shim (old: `from Tools.refresh import refresh_alltool`).

Canonical implementation lives in Tools/system.py (`alltool refresh`).
Kept so existing installs/scripts importing this path don't break.
"""
from .system import refresh as _refresh


def refresh_alltool(args=None):
    """Legacy entry point used by pre-2.0 AllTools.py. Delegates to system.refresh."""
    return _refresh(list(args) if args is not None else [])


__all__ = ["refresh_alltool"]
