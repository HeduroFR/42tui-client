"""Production composition; feature services never construct their own adapters."""
from ft_tui.features.accounts.service import AccountService


def build_account_service():
    return AccountService()


def build_catalog_service(session_factory):
    from ft_tui.features.catalog.service import CatalogService
    from ft_tui.features.catalog.adapters.sqlite import SqliteCatalogRepository
    return CatalogService(SqliteCatalogRepository(session_factory))


def build_profile_service(session_factory, catalog_service):
    from ft_tui.features.profiles.service import ProfileService
    from ft_tui.features.profiles.adapters.sqlite import SqliteProfileRepository
    return ProfileService(SqliteProfileRepository(session_factory), catalog_service)


def build_dashboard_service(session_factory):
    from pathlib import Path
    from ft_tui.features.dashboard.service import DashboardService
    from ft_tui.features.dashboard.adapters.sqlite import SqliteDashboardReader
    return DashboardService(SqliteDashboardReader(session_factory),
                            folder_exists=lambda path: bool(path and Path(path).expanduser().is_dir()))


def build_worklog_service(session_factory):
    from ft_tui.features.worklog.service import WorklogService
    from ft_tui.features.worklog.adapters.sqlite import SqliteWorklogRepository
    return WorklogService(SqliteWorklogRepository(session_factory))


def build_project_service(session_factory):
    from ft_tui.features.projects.service import ProjectService
    from ft_tui.features.projects.adapters.sqlite import SqliteProjectRepository
    from ft_tui.features.projects.adapters.checkout import setup_project_checkout
    return ProjectService(SqliteProjectRepository(session_factory),setup_project_checkout)


def build_friends_service(session_factory):
    from ft_tui.features.friends.adapters.factory import create_friends_service
    return create_friends_service(session_factory)


def build_clubs_service():
    from ft_tui.features.clubs.service import ClubsService
    return ClubsService()


def build_social_service(session_factory):
    from ft_tui.features.social.service import SocialService
    from ft_tui.features.social.adapters.sqlite import SqliteSocialRepository
    return SocialService(SqliteSocialRepository(session_factory))


def build_cluster_service(session_factory, configured_cursus=None):
    from ft_tui.features.cluster_map.service import ClusterService
    from ft_tui.features.cluster_map.adapters.sqlite import SqliteClusterRepository
    return ClusterService(SqliteClusterRepository(session_factory, configured_cursus))


def build_corrections_service():
    from ft_tui.features.corrections.service import CorrectionsService
    return CorrectionsService()


def build_settings_service(session_factory):
    from ft_tui.features.settings.service import SettingsService
    from ft_tui.features.settings.adapters.sqlite import SqliteSettingsRepository
    return SettingsService(SqliteSettingsRepository(session_factory))


def build_installation_service(session_factory):
    from ft_tui.features.installation.service import InstallationService
    from ft_tui.features.settings.adapters.sqlite import SqliteSettingsRepository
    return InstallationService(SqliteSettingsRepository(session_factory))


def build_registration_service():
    from ft_tui.features.projects.registration.service import RegistrationService
    return RegistrationService()


def build_student_profile_service():
    from ft_tui.features.profiles.student_service import StudentProfileService
    from ft_tui.features.profiles.adapters.portraits import download_portrait
    return StudentProfileService(portrait_loader=download_portrait)


def build_subject_service(session_factory):
    from ft_tui.features.projects.subjects.service import SubjectService
    from ft_tui.features.projects.subjects.adapters.sqlite import SqliteSubjectRepository
    from ft_tui.features.projects.subjects.adapters.files import SubjectFiles
    return SubjectService(SqliteSubjectRepository(session_factory), SubjectFiles())


def build_activity_service(session_factory=None, configured_cursus=None):
    from ft_tui.features.projects.activity.service import ActivityService
    from ft_tui.features.projects.activity.adapters.sqlite import SqliteActivityContext
    return ActivityService(SqliteActivityContext(session_factory, configured_cursus))


def build_account_shell_service(session_factory):
    from ft_tui.features.accounts.shell_service import AccountShellService
    from ft_tui.features.accounts.adapters.shell import SqliteAccountShellRepository
    return AccountShellService(SqliteAccountShellRepository(session_factory))


def build_startup_service(session_factory):
    from ft_tui.app.startup import StartupService
    from ft_tui.infrastructure.startup import SqliteStartupRepository
    return StartupService(SqliteStartupRepository(session_factory))
