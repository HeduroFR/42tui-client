"""Headless startup acknowledgement, update opt-in and cooldown policy."""
from .models import CHECK_INTERVAL,stable_version
from .ports import InstallationPreferences


class InstallationService:
    def __init__(self,preferences: InstallationPreferences):
        self.preferences=preferences

    def enabled(self):
        return self.preferences.get('automatic_updates','true')!='false'

    def startup(self,current):
        previous=self.preferences.get('updates:last_seen_version')
        if not stable_version(previous) or stable_version(previous)>stable_version(current):
            self.preferences.save({'updates:last_seen_version':current})
        elif stable_version(previous)<stable_version(current):
            return previous
        return None

    def acknowledge(self,current):
        self.preferences.save({'updates:last_seen_version':current})

    def begin_check(self,now,*,force=False):
        try:last_check=float(self.preferences.get('updates:last_check','0'))
        except ValueError:last_check=0
        if not force and 0<=now-last_check<CHECK_INTERVAL:return False
        # Record before external work, including offline/failed attempts.
        self.preferences.save({'updates:last_check':str(now)})
        return True

    def newer(self,available,current):
        return bool(stable_version(available) and stable_version(available)>stable_version(current))
