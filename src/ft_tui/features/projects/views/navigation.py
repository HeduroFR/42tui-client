"""ProjectNavigation actions for the Projects screen."""

from textual.widgets import DataTable, Input as TextInput, Tabs
from ft_tui.ui.select import AppSelect

from ft_tui.ui.components import (
    Button,
    Input,
    ListView,
    Path,
    TabbedContent,
    TextArea,
    shutil,
    subprocess,
)


class ProjectNavigationMixin:
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"move_project_down", "move_project_up", "move_project_page_down",
                      "move_project_page_up", "first_project", "last_project"}:
            if not self.is_mounted:
                return False
            if self.focused and any(isinstance(node, (TextInput, TextArea, AppSelect))
                                    for node in self.focused.ancestors_with_self):
                return False
            return self._navigation_list() is not None
        return super().check_action(action, parameters)

    def action_open_project_editor(self) -> None:
        self._open_selected_project_in_editor()

    def _open_selected_project_in_editor(self) -> None:
        """Open the selected project folder using the configured favorite editor."""
        project = self.projects.get(self.selected_project_key or "")
        if project is None or not project.local_path:
            self.notify("Configure this project's local folder first.", severity="warning")
            return
        project_path = Path(project.local_path).expanduser()
        if not project_path.is_dir():
            self.notify("The configured project folder does not exist.", severity="error")
            return

        editor_commands = {
            "nvim": ("nvim", True),
            "vim": ("vim", True),
            "vscode": ("code", False),
            "zed": ("zed", False),
        }
        command, terminal_editor = editor_commands[self.favorite_editor]
        executable = shutil.which(command)
        if executable is None:
            self.notify(f"{command} was not found on PATH.", severity="error")
            return

        args = [executable]
        if terminal_editor:
            args.append(".")
        elif self.favorite_editor == "vscode":
            args.extend(("--reuse-window", str(project_path)))
        elif self.favorite_editor == "zed":
            args.append(str(project_path))
        try:
            if terminal_editor:
                if self.activity_refresh_timer is not None:
                    self.activity_refresh_timer.pause()
                editor_button = self.query_one("#open-project-editor", Button)
                button_pointer = editor_button.styles.pointer
                try:
                    # Textual uses Kitty's pointer-shape protocol for buttons. Reset
                    # it before handing the terminal to Neovim/Vim.
                    editor_button.styles.pointer = "default"
                    self.screen.update_pointer_shape()
                    with self.suspend():
                        result = subprocess.run(args, cwd=project_path, check=False)
                finally:
                    editor_button.styles.pointer = button_pointer
                    self.screen.update_pointer_shape()
                    if self.activity_refresh_timer is not None:
                        self.activity_refresh_timer.resume()
                    # Force a full repaint after the child editor has used the terminal.
                    self.refresh(layout=True)
                if result.returncode:
                    self.notify(f"{command} exited with status {result.returncode}.", severity="error")
            else:
                subprocess.Popen(
                    args,
                    cwd=project_path,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except OSError as error:
            self.notify(f"Could not open {project.name} in {command}: {error}", severity="error")

    def action_move_project_down(self) -> None:
        self._move_project_cursor(1)

    def action_move_project_up(self) -> None:
        self._move_project_cursor(-1)

    def action_move_project_page_down(self) -> None:
        self._move_project_cursor(8)

    def action_move_project_page_up(self) -> None:
        self._move_project_cursor(-8)

    def action_focus_project_search(self) -> None:
        self.query_one("#project-search", Input).focus()

    def action_first_project(self) -> None:
        self._move_project_cursor(to_row=0)

    def action_last_project(self) -> None:
        self._move_project_cursor(last=True)

    def _navigation_list(self):
        if len(self.screen_stack) > 1:
            return None
        pane = self.query_one(TabbedContent).active_pane
        if pane is None:
            return None
        lists = [widget for widget in pane.query("DataTable, ListView")
                 if not widget.disabled and all(node.display and node.visible for node in widget.ancestors_with_self)]
        return self.focused if self.focused in lists else next(iter(lists), None)

    def _move_project_cursor(self, offset: int = 0, to_row: int | None = None, *, last: bool = False) -> None:
        listing = self._navigation_list()
        if listing is None:
            return
        was_focused = listing.has_focus
        listing.focus()
        item_count = listing.row_count if isinstance(listing, DataTable) else len(listing.children)
        if item_count == 0:
            return
        current_row = listing.cursor_row if isinstance(listing, DataTable) else listing.index
        current_row = current_row if current_row is not None else 0
        # The first j/k enters the list without skipping its selected row.
        if not was_focused and to_row is None and not last and abs(offset) == 1:
            row = current_row
        else:
            row = item_count - 1 if last else to_row if to_row is not None else current_row + offset
        row = max(0, min(row, item_count - 1))
        if isinstance(listing, DataTable):
            listing.move_cursor(row=row)
        else:
            listing.index = row

    def action_tab_left(self) -> None:
        self._move_tab(-1)

    def action_tab_right(self) -> None:
        self._move_tab(1)

    def _move_tab(self, offset: int) -> None:
        if len(self.screen_stack) > 1:
            return
        tabs = self.query_one(TabbedContent).query_one(Tabs)
        # Release the outgoing pane before hiding it; its focus notifications
        # would otherwise reactivate that pane after the tab change.
        tabs.focus()
        if offset > 0:
            tabs.action_next_tab()
        elif offset < 0:
            tabs.action_previous_tab()

    def _activate_main_tab(self, pane_id: str) -> None:
        if len(self.screen_stack) > 1:
            return
        content = self.query_one(TabbedContent)
        content.query_one(Tabs).focus()
        content.active = pane_id
