"""Run the complete unittest suite in explicit, non-overlapping feature scopes."""
import argparse
from collections import Counter
from fnmatch import fnmatchcase
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Assign by responsibility, not filename hash or test index. New modules require
# an explicit owner; --check fails on omissions, duplicates and stale entries.
SCOPES = {
    'accounts': (
        'test_api_error_diagnostics', 'test_api_settings', 'test_client_factory',
        'test_http_client', 'test_keychain', 'test_oauth_client', 'test_account_service', 'test_account_shell_service',
        'test_oauth_session_simulation', 'test_oauth_ui_locales',
        'test_onboarding_language', 'test_ui_account_connection', 'test_ui_campus_settings',
    ),
    'friends': (
        'test_friend_directory', 'test_friends', 'test_friends_refresh', 'test_friends_feature_service', 'test_friends_feature_repository',
        'test_friend_cache_origin', 'test_student_search', 'test_ui_friend_project',
        'test_ui_friend_suggestions', 'test_ui_friends',
    ),
    'clubs-social': (
        'test_clubs_provider', 'test_social_provider', 'test_social_simulation',
        'test_clubs_feature', 'test_social_feature_service', 'test_social_feature_repository', 'test_community_composition',
        'test_ui_clubs', 'test_ui_social',
    ),
    'profiles': ('test_student_profile_feature_service', 'test_ui_user_profile', 'test_user_profile', 'test_profile_service', 'test_profile_repository'),
    'catalog-curriculum': (
        'test_catalog_cache_controller', 'test_catalog_cache_simulation',
        'test_catalog_service', 'test_catalog_repository',
        'test_catalog_metadata', 'test_catalog_provider', 'test_catalog_store',
        'test_curriculum_selection', 'test_project_curriculum',
        'test_ui_catalog_details', 'test_ui_curriculum_settings',
    ),
    'projects': (
        'test_project_registration_feature_service', 'test_project_subject_feature_service',
        'test_project_subject_feature_boundaries', 'test_project_activity_feature_service',
        'test_project_activity_feature_boundaries', 'test_activity_presentation', 'test_activity_provider', 'test_project_kind',
        'test_registration_cache', 'test_registration_presentation',
        'test_registration_provider', 'test_subject_sync', 'test_ui_fuzzy_projects',
        'test_ui_project_activity', 'test_ui_project_browser', 'test_ui_project_details_layout',
        'test_ui_project_rank', 'test_ui_project_registration', 'test_ui_project_team',
        'test_ui_subject_refresh',
    ),
    'dashboard': (
        'test_dashboard_cache', 'test_goals_types', 'test_dashboard_service',
        'test_dashboard_repository', 'test_dashboard_feature_wiring',
        'test_ui_dashboard_portrait', 'test_ui_dashboard_profile',
    ),
    'cluster': (
        'test_cluster_feature_service', 'test_cluster_feature_boundaries', 'test_campus_composition', 'test_cluster_experience', 'test_cluster_map_api', 'test_cluster_map_geometry',
        'test_cluster_map_journey', 'test_cluster_map_state', 'test_cluster_portrait',
        'test_current_location', 'test_ui_cluster_issue', 'test_ui_cluster_map',
        'test_ui_cluster_workstation',
    ),
    'corrections': ('test_corrections_feature_service', 'test_slots_*', 'test_ui_correction_slots', 'test_ui_slots_calendar'),
    'widgets': (
        'test_fuzzy_search', 'test_ui_buttons', 'test_ui_modals',
        'test_ui_selects', 'test_ui_tab_navigation',
    ),
    'settings-navigation': (
        'test_settings_feature_service', 'test_terminal_capabilities', 'test_ui_settings_navigation',
        'test_ui_terminal_settings', 'test_ui_username',
    ),
    'testers': ('test_tester_terminal', 'test_testers', 'test_ui_project_testers'),
    'installation-updates': (
        'test_installation_feature_service', 'test_installation_feature_boundaries', 'test_installer', 'test_installer_bootstrap', 'test_installer_lifecycle',
        'test_installer_uninstall', 'test_updates', 'test_ui_updates',
    ),
    'release-tooling': (
        'test_canonical_imports', 'test_shell_architecture', 'test_shell_startup_service', 'test_shell_startup_repository', 'test_workflow_composition', 'test_preferences_composition', 'test_architecture_context', 'test_architecture_boundaries', 'test_read_context',
        'test_fixture_portability', 'test_regression_scopes', 'test_release_cli',
        'test_release_retry', 'test_release_validation', 'test_services', 'test_worklog_feature', 'test_project_feature', 'test_worklog_ui',
        'test_read_cache', 'test_ui_read_cache',
    ),
}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def partition_tests(tests, discovered_modules, scopes=None):
    scopes = SCOPES if scopes is None else scopes
    owners = {}
    for scope, modules in scopes.items():
        for rule in modules:
            matches = {module for module in discovered_modules if fnmatchcase(module, rule)}
            if not matches:
                raise ValueError(f'Removed/renamed module or unmatched scope rule: {rule}')
            for module in matches:
                if module in owners:
                    raise ValueError(f'{module} is assigned to multiple scopes: {owners[module]}, {scope}')
                owners[module] = scope
    missing = discovered_modules - owners.keys()
    if missing:
        raise ValueError(f'Unassigned modules: {sorted(missing)}')
    tests = list(tests)
    duplicates = [name for name, count in Counter(test.id() for test in tests).items() if count > 1]
    if duplicates:
        raise ValueError(f'Duplicate test identities in discovery: {sorted(duplicates)}')
    selected = {scope: [] for scope in scopes}
    for test in tests:
        # unittest discover -s tests imports modules at the discovery root.
        module = type(test).__module__.removeprefix('tests.')
        if module not in owners:
            raise ValueError(f'Unassigned test module: {module} ({test.id()})')
        selected[owners[module]].append(test)
    if any(not cases for cases in selected.values()):
        raise ValueError('Every regression scope must contain at least one discovered test')
    return selected


def discover_plan(directory=ROOT/'tests', scopes=None):
    loader = unittest.TestLoader()
    suite = loader.discover(str(directory), pattern='test*.py')
    if loader.errors:
        raise ValueError('Test discovery failed:\n' + '\n'.join(loader.errors))
    modules = {path.stem for path in directory.glob('test*.py')}
    return partition_tests(flatten(suite), modules, scopes)


def run_scope(scope, directory=ROOT/'tests', scopes=None, *, durations=20):
    plan = discover_plan(directory, scopes)
    if scope not in plan:
        raise ValueError(f'Unknown scope: {scope}')
    selected = plan[scope]
    print(f'Running {scope}: {len(selected)} tests; all {sum(map(len, plan.values()))} discovered tests assigned exactly once.', flush=True)
    result = unittest.TextTestRunner(verbosity=2, durations=durations).run(unittest.TestSuite(selected))
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--matrix', action='store_true', help='export the validated GitHub Actions matrix as JSON')
    mode.add_argument('--check', action='store_true', help='validate all scope assignments without running tests')
    mode.add_argument('--scope', choices=SCOPES, help='run one required feature scope')
    parser.add_argument('--durations', type=int, default=20, help='show N slowest tests (default: 20)')
    args = parser.parse_args(argv)
    try:
        if args.check or args.matrix:
            plan = discover_plan()
            if args.matrix:
                print(json.dumps({'scope': list(plan)}))
                return 0
            for scope, cases in plan.items():
                print(f'{scope}: {len(cases)} tests')
            print(f'Total: {sum(map(len, plan.values()))} tests; complete, non-overlapping coverage.')
            return 0
        return run_scope(args.scope, durations=args.durations)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
