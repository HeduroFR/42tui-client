"""Local workspace preferences, shared by settings presentation and app lifecycle."""
from dataclasses import dataclass,field
from pathlib import Path

@dataclass
class SettingsState:
    projects_root: str = field(default_factory=lambda: str(Path.home()/'42'))
    favorite_editor: str = 'nvim'
    favorite_subject_viewer: str = 'system'
    language: str = 'en'
    club_notification_sound: bool = True
    image_mode: str = 'auto'
    icon_mode: str = 'auto'
    username_gradient: str = 'off'
    subject_check_interval_seconds: int = 21600
