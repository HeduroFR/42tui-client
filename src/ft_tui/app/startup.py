"""Portable startup snapshots; the shell retains lifecycle and rendering order."""
import json
from typing import Protocol
from ft_tui.features.accounts.campuses import campus_directory

LEGACY_PREFERENCES=('projects_root','favorite_editor','favorite_theme','language')
INITIAL_KEYS=(*LEGACY_PREFERENCES,'onboarding_completed','campus_directory','club_notification_sound',
              'companion_visible','companion_motion','image_mode','icon_mode','username_gradient','catalog_last_account','catalog_last_campuses')
MOUNT_KEYS=(*LEGACY_PREFERENCES,'onboarding_completed','favorite_subject_viewer','subject_check_interval_seconds')


class StartupRepository(Protocol):
    def preferences(self,keys) -> dict: ...
    def save(self,values): ...
    def cached_cursuses(self): ...
    def catalog(self,cursus,account,campus,*,allow_cached_owner=True): ...
    def branches(self,cursus,campus,track): ...


class StartupService:
    def __init__(self,repository: StartupRepository):self.repository=repository

    def initial_preferences(self,detected_language):
        values=self.repository.preferences(INITIAL_KEYS)
        first=values.get('onboarding_completed','')!='true' and not any(key in values for key in LEGACY_PREFERENCES)
        try:campuses=campus_directory({'campuses':json.loads(values.get('campus_directory','[]'))})
        except (ValueError,TypeError):campuses=[]
        try:account_campuses=json.loads(values.get('catalog_last_campuses','[]'))
        except ValueError:account_campuses=[]
        return {
            'first_launch':first,'campus_directory':campuses,
            'language':values.get('language',detected_language if first else 'en'),
            'club_notification_sound':values.get('club_notification_sound','true')=='true',
            'companion_visible':values.get('companion_visible','true')=='true',
            'companion_motion':values.get('companion_motion','true')=='true',
            'image_mode':values.get('image_mode','auto'),'icon_mode':values.get('icon_mode','auto'),
            'username_gradient':values.get('username_gradient','off'),
            'offline_account_id':values.get('catalog_last_account') or None,
            'offline_account_campuses':account_campuses,
        }

    def mount_preferences(self,current_language,projects_root,favorite_editor,theme,default_subject_interval):
        values=self.repository.preferences(MOUNT_KEYS)
        complete=values.get('onboarding_completed','')=='true'
        existing=any(key in values for key in LEGACY_PREFERENCES)
        pending=not complete and not existing
        if not complete and existing:self.repository.save({'onboarding_completed':'true'})
        return {
            'onboarding_pending':pending,
            'language':values.get('language',current_language if pending else 'en'),
            'projects_root':values.get('projects_root',projects_root),
            'favorite_editor':values.get('favorite_editor',favorite_editor),
            'favorite_subject_viewer':values.get('favorite_subject_viewer','system'),
            'subject_interval':values.get('subject_check_interval_seconds',str(default_subject_interval)),
            'favorite_theme':values.get('favorite_theme',theme),
        }

    def cached_cursuses(self):return self.repository.cached_cursuses()

    def catalog(self,cursus,account,campus,*,allow_cached_owner=True):
        return self.repository.catalog(cursus,account,campus,allow_cached_owner=allow_cached_owner)

    def branches(self,cursus,campus,track):return self.repository.branches(cursus,campus,track)

    def finish_onboarding(self,language,values):
        settings={'onboarding_completed':'true','language':language}
        if values is not None:settings.update(values)
        self.repository.save(settings)

    def has_saved_cursus_selection(self):
        return bool(self.repository.preferences(('default_cursus_id',)).get('default_cursus_id',''))
