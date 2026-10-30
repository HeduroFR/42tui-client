"""Settings UI composition and behavior."""

import asyncio
import webbrowser
from collections.abc import Iterable
from ft_tui.ui.username import USERNAME_GRADIENTS, username_text

from ft_tui.api.client_interface import CursusSnapshot
from ft_tui.ui.terminal_capabilities import (
    IMAGE_MODES, ICON_MODES, valid_mode,
)
from ft_tui.ui.components import (
    Button,
    DEFAULT_SUBJECT_CHECK_INTERVAL,
    Horizontal,
    LANGUAGE_LABELS,
    SUBJECT_CHECK_INTERVALS,
    SUPPORTED_LANGUAGES,
    ListView,
    Input,
    Select,
    Static,
    Vertical,
)


from textual import on
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import ListItem


SETTINGS_CATEGORIES = (
    ("account", "Account"),
    ("curriculum", "Curriculum"),
    ("workspace", "Workspace"),
    ("subjects", "Subjects"),
    ("appearance", "Appearance"),
    ("community", "Community"),
)

SETTINGS_DESCRIPTIONS = {
    "account": "Manage your 42 connection and data source.",
    "curriculum": "Choose the cursus, campus and catalog used for projects.",
    "workspace": "Choose project folders, your editor and updates.",
    "subjects": "Configure subject downloads and the PDF viewer.",
    "appearance": "Personalize the interface and terminal display.",
    "community": "Visit the project and its community.",
}


class SettingsCategories(ListView):
    """Category selection follows the cursor; Enter opens its controls."""

    BINDINGS = [Binding("right", "select_cursor", show=False)]


class SettingsWorkspace(Vertical):
    """A keyboard workspace with persistent fields and a fixed action bar."""

    BINDINGS = [
        Binding("escape", "categories", show=False),
        Binding("ctrl+s", "save", "Save settings", priority=True),
    ]

    def on_mount(self) -> None:
        from ft_tui.ui.theme_preview import watch_theme_preview
        watch_theme_preview(self, self.query_one('#favorite-theme', Select))
        self.show_category(0)
        for name in ('github', 'discord'):
            self.query_one(f'#community-{name}-reminder').display = (
                self.app._settings_operations().get(f'community_{name}_reminder_seen') != 'true')

    def on_resize(self) -> None:
        self.set_class(self.size.width < 78, "compact")
        self.set_class(self.size.width < 52, "narrow-storage")

    def show_category(self, index: int) -> None:
        for position, (key, _) in enumerate(SETTINGS_CATEGORIES):
            self.query_one(f"#settings-panel-{key}").display = position == index
        key, label = SETTINGS_CATEGORIES[index]
        self.query_one("#settings-category-title", Static).update(label)
        self.query_one("#settings-category-description", Static).update(SETTINGS_DESCRIPTIONS[key])
        self.query_one("#settings-content", VerticalScroll).scroll_home(animate=False)
        self.app._refresh_username_preview()

    @on(ListView.Highlighted, "#settings-categories")
    def category_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self.show_category(event.list_view.index)
        event.stop()

    @on(ListView.Selected, "#settings-categories")
    def edit_category(self, event: ListView.Selected) -> None:
        for panel in self.query(".settings-panel"):
            if panel.display:
                for field in panel.query("Input, Select, Button"):
                    if field.focusable:
                        field.focus()
                        break
        event.stop()

    def action_categories(self) -> None:
        self.query_one("#settings-categories", ListView).focus()

    async def action_save(self) -> None:
        await self.app._save_settings_and_refresh_projects()

    @on(Button.Pressed, '#settings-storage-apply')
    def change_session_storage(self, event):
        from ft_tui.features.accounts.adapters.storage_transfer import storage_kind
        from ft_tui.features.accounts.views.connection import VaultPassphraseScreen
        event.stop()
        client = self.app.oauth_client
        kind = self.query_one('#settings-storage', Select).value
        if not self.app.account_connected or client is None or kind == storage_kind(client.store):
            return
        self._storage_source = client.store
        if kind == 'vault':
            self.app.push_screen(VaultPassphraseScreen(False), self._storage_passphrase)
        else:
            self.run_worker(self._move_storage(kind), group='settings-session-storage', exclusive=True)

    def _storage_passphrase(self, value):
        if value is not None and self.is_mounted:
            self.run_worker(self._move_storage('vault', value), group='settings-session-storage', exclusive=True)

    async def _move_storage(self, kind, passphrase=None):
        from ft_tui.features.accounts.adapters.storage_transfer import move_session, storage_kind
        button = self.query_one('#settings-storage-apply', Button)
        selector = self.query_one('#settings-storage', Select)
        status = self.query_one('#settings-storage-status', Static)
        button.disabled = selector.disabled = True
        client = self.app.oauth_client
        try:
            await asyncio.to_thread(move_session, client, kind, passphrase, self._storage_source)
        except Exception:
            status.update('Could not move the session. Check both stores before retrying.')
        else:
            status.update('Session storage updated.')
        finally:
            if self.is_mounted:
                current = storage_kind(client.store)
                if current:
                    with self.prevent(Select.Changed):
                        selector.value = current
                button.disabled = selector.disabled = False

    @on(Button.Pressed, '#community-github, #community-discord, #community-github-dismiss, #community-discord-dismiss')
    async def community_action(self, event):
        event.stop()
        name = 'github' if 'github' in event.button.id else 'discord'
        status = self.query_one('#community-status', Static)
        if event.button.id.endswith('-dismiss'):
            try:
                self.app._settings_operations().save_values({f'community_{name}_reminder_seen': 'true'})
            except Exception:
                status.update('Could not save the reminder. Please try again.')
                return
            self.query_one(f'#community-{name}-reminder').display = False
            status.update('Reminder dismissed.')
            return
        url = ('https://github.com/HeduroFR/42tui-client' if name == 'github'
               else 'https://tui.42wip.in/discord')
        try:
            opened = await asyncio.to_thread(webbrowser.open, url)
        except Exception:
            opened = False
        status.update('Opened in your browser.' if opened else 'Could not open a browser. Use the displayed link.')

    @on(Select.Changed, '#favorite-theme')
    def theme_preview_changed(self, event):
        if event.value in self.app.available_themes:
            self.app.theme = event.value
        event.stop()

    @on(Select.Changed, '#username-gradient')
    def username_preview_changed(self, event):
        event.stop()
        self.app._refresh_username_preview()


class SettingsMixin:
    def _settings_operations(self):
        service = getattr(self, 'settings_service', None)
        if service is None:
            from ft_tui.app.bootstrap import build_settings_service
            service = build_settings_service(self.session_factory)
        return service

    def compose_settings(self):
        """Keep every field mounted so drafts survive category changes."""
        with SettingsWorkspace(id="settings-workspace"):
            with Horizontal(id="settings-topbar"):
                yield Static("SETTINGS", id="settings-heading")
            with Horizontal(id="settings-body"):
                with Vertical(id="settings-sidebar"):
                    yield Static("CATEGORIES", id="settings-nav-heading", classes="section-kicker")
                    yield SettingsCategories(
                        *(ListItem(Static(label), id=f"settings-nav-{key}") for key, label in SETTINGS_CATEGORIES),
                        id="settings-categories",
                    )
                with VerticalScroll(id="settings-content"):
                    yield Static("Account", id="settings-category-title")
                    yield Static(SETTINGS_DESCRIPTIONS["account"], id="settings-category-description")
                    with Vertical(id="settings-panel-account", classes="settings-panel"):
                        with Vertical(id="settings-profile-card", classes="settings-section"):
                            yield Static("PROFILE", classes="section-kicker")
                            yield Static("42 account", classes="settings-label")
                            yield Static("Not connected", id="account-connection-state")
                            yield Button("Connect 42 account", id="settings-connect-account", variant="primary")
                            yield Static(
                                "Connect securely in your browser. Your password and OAuth code stay with 42.",
                                classes="field-help",
                            )
                        with Vertical(id="settings-storage-card", classes="settings-section"):
                            yield Static("Session storage", classes="section-kicker")
                            with Horizontal(id="settings-storage-row"):
                                yield Select([("OS keyring", "keyring"), ("This session only", "session"),
                                              ("Remember with a passphrase", "vault")],
                                             value="keyring", allow_blank=False, id="settings-storage")
                                yield Button("Move session", id="settings-storage-apply")
                            yield Static("Moving to this session only removes the saved session from this device.", classes="field-help")
                            yield Static("", id="settings-storage-status")
                        with Vertical(id="provider-card"):
                            yield Static("DATA SOURCE", classes="section-kicker")
                            yield Static("42 account not connected", id="provider-title")
                            yield Static(
                                "Your saved projects and activity stay on this device. Connect your "
                                "42 account to sync your real projects.",
                                id="provider-description",
                                classes="field-help",
                            )
                    with Vertical(id="settings-panel-curriculum", classes="settings-panel"):
                        with Vertical(id="settings-cursus-card", classes="settings-section"):
                            yield Static("Curriculum", classes="section-kicker")
                            yield Static("Default cursus", classes="settings-label")
                            yield Static(
                                "Choose the cursus used to filter your project list.",
                                classes="field-help",
                            )
                            saved_cursus_id = self._settings_operations().get("default_cursus_id")
                            saved_cursus_options = (
                                [
                                    (
                                        "Saved cursus (unavailable)",
                                        saved_cursus_id,
                                    )
                                ]
                                if saved_cursus_id
                                else []
                            )
                            yield Select(
                                saved_cursus_options,
                                value=saved_cursus_id if saved_cursus_id else Select.NULL,
                                prompt="Select cursus",
                                id="default-cursus",
                            )
                            yield Static("Loading cursus list…", id="default-cursus-status")
                            yield Static("Campus", classes="settings-label")
                            yield Select([], prompt="Select campus", localize_options=False, id="catalog-campus")
                        with Vertical(id="settings-catalog-card", classes="settings-section"):
                            yield Static("Catalog", classes="section-kicker")
                            yield Static("Common Core fallback", classes="settings-label")
                            yield Select([("Automatic evidence", "auto"), ("Old", "old"), ("New", "new")], value="auto", allow_blank=False, id="cc-default-track")
                            yield Static("", id="cc-context-status")
                            yield Button("Refresh catalog", id="settings-refresh-catalog")
                            yield Static("Download the latest catalog, bypassing the local cache.", classes="field-help")
                    with Vertical(id="settings-panel-workspace", classes="settings-panel"):
                        with Vertical(id="settings-workspace-card", classes="settings-section"):
                            yield Static("PROJECT WORKSPACE", classes="section-kicker")
                            yield Static("Default projects folder", classes="settings-label")
                            yield Input(placeholder="/home/user/42", id="projects-root")
                            yield Static(
                                "New project setups will suggest this folder.",
                                classes="field-help",
                            )
                        with Vertical(id="settings-editor-card", classes="settings-section"):
                            yield Static("EDITOR", classes="section-kicker")
                            yield Static("Favorite code editor", classes="settings-label")
                            yield Select(
                                [
                                    ("Neovim", "nvim"),
                                    ("Vim", "vim"),
                                    ("Visual Studio Code", "vscode"),
                                    ("Zed", "zed"),
                                ],
                                value="nvim",
                                id="favorite-editor",
                            )
                            yield Static(
                                "Used by the Open in editor action in project details.",
                                classes="field-help",
                            )
                        with Vertical(classes="settings-section"):
                            yield Static("Automatic updates", classes="settings-label")
                            automatic_updates = self._settings_operations().get("automatic_updates", "true")
                            yield Select([("Enabled", "true"), ("Disabled", "false")],
                                         value="false" if automatic_updates == "false" else "true",
                                         id="automatic-updates")
                            yield Static("Install stable updates before opening 42TUI. Development installs are skipped.",
                                         classes="field-help")
                    with Vertical(id="settings-panel-subjects", classes="settings-panel"):
                        with Vertical(
                            id="settings-subject-card", classes="settings-section"
                        ):
                            yield Static("SUBJECT PDFs", classes="section-kicker")
                            yield Static("Subject PDF auto-check", classes="settings-label")
                            yield Select(
                                [
                                    (label, seconds)
                                    for seconds, label in SUBJECT_CHECK_INTERVALS.items()
                                ],
                                value=str(DEFAULT_SUBJECT_CHECK_INTERVAL),
                                id="subject-check-interval",
                            )
                            yield Static(
                                "Checks <project folder>/subject.pdf and downloads it when the "
                                "configured provider supports subject files.",
                                classes="field-help",
                            )
                            yield Static("Subject PDF viewer", classes="settings-label")
                            yield Select(
                                [("System default app", "system"), ("TDF in terminal", "tdf")],
                                value="system",
                                id="subject-viewer",
                            )
                            yield Static(
                                "TDF must be installed and available on PATH; System default uses "
                                "your OS PDF application.",
                                classes="field-help",
                            )
                    with Vertical(id="settings-panel-appearance", classes="settings-panel"):
                        with Vertical(
                            id="settings-appearance-card",
                            classes="settings-section",
                        ):
                            yield Static("APPEARANCE", classes="section-kicker")
                            yield Static("Language", classes="settings-label")
                            yield Select(
                                [(LANGUAGE_LABELS[code], code) for code in SUPPORTED_LANGUAGES],
                                value="en",
                                allow_blank=False,
                                id="interface-language",
                            )
                            yield Static("Favorite theme", classes="settings-label")
                            yield Select(
                                [
                                    (name.replace("-", " ").title(), name)
                                    for name in sorted(self.available_themes)
                                ],
                                value=self.theme,
                                id="favorite-theme",
                            )
                            yield Static('Username gradient', classes='settings-label')
                            yield Select(
                                [(label, key) for key, (label, _) in USERNAME_GRADIENTS.items()],
                                value=self.username_gradient, allow_blank=False, id='username-gradient',
                            )
                            yield Static('', id='username-gradient-preview', markup=False, localize=False)
                            yield Static('Preview your dashboard username. Save settings to apply.', id='username-gradient-help', classes='field-help')
                        with Vertical(id="settings-terminal-card", classes="settings-section"):
                            yield Static("Terminal display", classes="section-kicker")
                            yield Static('Images', classes='settings-label')
                            yield Select([
                                ('Automatic', 'auto'), ('Sixel', 'sixel'), ('Kitty graphics', 'tgp'),
                                ('Colored blocks', 'halfcell'), ('Off', 'off'),
                            ], value=self.image_mode, id='terminal-images')
                            yield Static('Icons', classes='settings-label')
                            yield Select([
                                ('Automatic', 'auto'), ('Nerd Font', 'nerd'),
                                ('Simple Unicode', 'unicode'), ('Text only', 'text'),
                            ], value=self.icon_mode, id='terminal-icons')
                        with Vertical(id="settings-sound-card", classes="settings-section"):
                            yield Static("Notifications", classes="section-kicker")
                            yield Static("Notification sound", classes="settings-label")
                            yield Select(
                                [("On", "true"), ("Off", "false")],
                                value="true" if self.club_notification_sound else "false",
                                id="club-notification-sound",
                            )
                            yield Static(
                                "Uses the terminal bell. Enable audible bell in your terminal settings.",
                                classes="field-help",
                            )
                    with Vertical(id="settings-panel-community", classes="settings-panel"):
                        with Vertical(classes="settings-section"):
                            yield Static("GitHub", classes="section-kicker")
                            yield Static("https://github.com/HeduroFR/42tui-client", markup=False, localize=False, classes="field-help")
                            yield Button("Open GitHub", id="community-github")
                            with Vertical(id="community-github-reminder"):
                                yield Static("Enjoy 42TUI? Consider starring the project on GitHub.", classes="field-help")
                                yield Button("Dismiss reminder", id="community-github-dismiss")
                        with Vertical(classes="settings-section"):
                            yield Static("Discord", classes="section-kicker")
                            yield Static("https://tui.42wip.in/discord", markup=False, localize=False, classes="field-help")
                            yield Button("Open Discord", id="community-discord")
                            with Vertical(id="community-discord-reminder"):
                                yield Static("Join the 42TUI community on Discord.", classes="field-help")
                                yield Button("Dismiss reminder", id="community-discord-dismiss")
                        yield Static("", id="community-status")
            with Horizontal(id="settings-actions"):
                yield Static("Save to keep preference changes.", id="settings-status")
                yield Button("Save settings", variant="primary", id="save-settings")
            yield Static("↑ ↓ Categories · Enter Edit · Tab Next field · Esc Categories · Ctrl+S Save", id="settings-help")


    async def _refresh_settings_catalog(self) -> None:
        if not self.account_connected or self.provider is None:
            self.notify("Connect your 42 account to refresh the catalog.", severity="warning")
            return
        if self._catalog_scope() is None:
            self.notify("Choose a campus in Settings.", severity="warning")
            return
        button = self.query_one("#settings-refresh-catalog", Button)
        button.disabled = True
        provider, generation = self.provider, self.account_generation
        try:
            await self._refresh_catalog_context(provider, generation, force=True)
            if provider is self.provider and generation == self.account_generation:
                if self.catalog_status == "Catalog unavailable. Showing saved data.":
                    self.notify(self.catalog_status, severity="warning")
                else:
                    self.notify("Catalog refreshed.")
        finally:
            button.disabled = False

    def set_cursus_choices(
        self,
        cursuses: Iterable[CursusSnapshot],
        *,
        loading: bool = False,
        available: bool = True,
    ) -> None:
        """Update the selector from an API or local cursus snapshot.

        The app refresh flow can call this without coupling selector state to API
        loading. A previously saved ID stays selectable if it is absent upstream.
        """
        if not self.is_mounted:
            return
        selector = self.query_one("#default-cursus", Select)
        status = self.query_one("#default-cursus-status", Static)

        selected = selector.value
        cursus_list = list(cursuses)
        options = [(str(cursus.name), str(cursus.id)) for cursus in cursus_list]
        option_ids = {value for _, value in options}
        unavailable_saved_id = None
        if selected not in (None, Select.NULL) and str(selected) not in option_ids:
            saved_id = str(selected)
            unavailable_saved_id = saved_id
            options.append(("Saved cursus (unavailable)", saved_id))
        with self.prevent(Select.Changed):
            selector.set_options(options)
            if selected not in (None, Select.NULL):
                selector.value = str(selected)

        if loading:
            status.update("Loading cursus list…")
        elif not available:
            status.update("Cursus list unavailable. Connect your 42 account to load cursus options.")
        elif unavailable_saved_id:
            # Static.update applies the locale template to this source message
            # once, retaining the English source for later language changes.
            status.update(f"Saved cursus unavailable (ID: {unavailable_saved_id})")
        elif not cursus_list:
            status.update("No cursus memberships found.")
        else:
            status.update("")
        status.display = loading or not available or bool(unavailable_saved_id) or not cursus_list

    def _clear_settings_status(self) -> None:
        self.settings_status_timer = None
        # A timer callback may already be queued when the screen is torn down.
        try:
            status = self.query_one("#settings-status", Static)
        except NoMatches:
            return
        status.update("")

    async def _save_settings(self) -> None:
        updates_were_enabled = self.automatic_updates_enabled()
        root_value = self.query_one("#projects-root", Input).value.strip()
        favorite_editor = str(self.query_one("#favorite-editor", Select).value)
        favorite_subject_viewer = str(self.query_one("#subject-viewer", Select).value)
        subject_interval = str(self.query_one("#subject-check-interval", Select).value)
        favorite_theme = str(self.query_one("#favorite-theme", Select).value)
        language = str(self.query_one("#interface-language", Select).value)
        club_sound = str(self.query_one("#club-notification-sound", Select).value)
        images = valid_mode(self.query_one('#terminal-images', Select).value, IMAGE_MODES)
        icons = valid_mode(self.query_one('#terminal-icons', Select).value, ICON_MODES)
        gradient = self.query_one('#username-gradient', Select).value
        gradient = gradient if gradient in USERNAME_GRADIENTS else 'off'
        default_cursus_id = self.query_one("#default-cursus", Select).value
        status = self.query_one("#settings-status", Static)
        campus_value = self.query_one("#catalog-campus", Select).value
        track_value = self.query_one("#cc-default-track", Select).value
        current_scope = self._catalog_scope()
        values = {
            "automatic_updates": str(self.query_one("#automatic-updates", Select).value),
            "projects_root": root_value,
            "favorite_editor": favorite_editor,
            "favorite_subject_viewer": favorite_subject_viewer,
            "subject_check_interval_seconds": subject_interval,
            "favorite_theme": favorite_theme,
            "language": language,
            "club_notification_sound": club_sound,
            'image_mode': images,
            'icon_mode': icons,
            'username_gradient': gradient,
            "default_cursus_id": (
                "" if default_cursus_id in (None, Select.NULL) else str(default_cursus_id)
            ),
            "default_cursus_source": "" if default_cursus_id in (None, Select.NULL) else "manual",
        }
        values['campus_id'] = None if campus_value in (None, Select.NULL) else int(campus_value)
        values['track'] = track_value
        try:
            values = self._settings_operations().save(values, account_id=self.account_id,
                campus_id=current_scope.campus_id if current_scope else None)
        except ValueError as error:
            status.update(str(error))
            return
        if values["automatic_updates"] == "false":
            self.pending_update = None
        elif not updates_were_enabled:
            self._start_update_check(force=True)
        self.projects_root = values["projects_root"]
        self.favorite_editor = favorite_editor
        self.favorite_subject_viewer = favorite_subject_viewer
        self.language = language
        self.club_notification_sound = club_sound == "true"
        images_changed = self.image_mode != images
        self.image_mode = images
        self.icon_mode = icons
        self.username_gradient = gradient
        if images_changed:
            from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
            from ft_tui.features.cluster_map.views.cluster_map_grid import ClusterMapGrid
            for portrait in list(self.query(ClusterPortrait)):
                await portrait.apply_terminal_settings()
            for grid in self.query(ClusterMapGrid):
                grid.refresh()
                grid._schedule_portraits()
        self.subject_check_interval_seconds = int(subject_interval)
        if self.subject_check_timer is not None:
            self.subject_check_timer.stop()
        self.subject_check_timer = self.set_interval(
            min(30, self.subject_check_interval_seconds),
            self._start_due_subject_checks,
        )
        self._start_due_subject_checks()
        self.theme = favorite_theme
        self._apply_language()
        self._refresh_username_preview()
        self._update_editor_button()
        self.query_one("#projects-root", Input).value = self.projects_root
        status.update("Settings saved locally.")
        if self.settings_status_timer is not None:
            self.settings_status_timer.stop()
        self.settings_status_timer = self.set_timer(3, self._clear_settings_status)
        self._update_black_hole()
        await self._refresh_dashboard()

    def _refresh_username_preview(self):
        self.query_one('#username-gradient-preview', Static).update(username_text(
            self.account_login or 'username', self.query_one('#username-gradient', Select).value,
        ))

    def _load_curriculum_setting_widgets(self):
        if not self.is_mounted:
            return
        scope = self._catalog_scope()
        service = self._settings_operations()
        track = service.track(self.account_id, scope.cursus_id, scope.campus_id) if scope else ''
        selector = self.query_one('#catalog-campus', Select)
        options, selected = service.campus_choices(self.campus_directory, self.account_campuses,
            campus_id=scope.campus_id if scope else None, fallback_label=self._campus_fallback_label())
        selected = selected if selected is not None else Select.NULL
        with self.prevent(Select.Changed):
            selector.set_options(options)
            selector.value = selected
            selector.disabled = not options
            self.query_one('#cc-default-track',Select).value = track if track in ('old','new') else 'auto'
        self.query_one('#cc-context-status',Static).update('Settings apply to this account, cursus and campus.')

    def _campus_fallback_label(self):
        from ft_tui.i18n import translate
        return translate('Saved campus (unavailable)', self.language)
