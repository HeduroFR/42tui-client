"""Read and write local key/value user settings."""

from sqlalchemy.orm import Session

from ft_tui.db.models import UserConfig


def get_setting(session: Session, key: str, default: str = "") -> str:
    """Return a setting value, or its default when it has not been saved."""
    setting = session.get(UserConfig, key)
    return setting.value if setting else default


def save_settings(session: Session, values: dict[str, str]) -> None:
    """Insert or update several local settings in one transaction."""
    for key, value in values.items():
        setting = session.get(UserConfig, key)
        if setting is None:
            session.add(UserConfig(key=key, value=value))
        else:
            setting.value = value
    session.commit()
