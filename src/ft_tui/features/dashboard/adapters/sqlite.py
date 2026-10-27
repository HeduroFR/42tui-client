"""Compatibility name for the worklog-owned local activity read adapter."""
from ft_tui.features.worklog.adapters.activity import SqliteActivityReader
SqliteDashboardReader = SqliteActivityReader
