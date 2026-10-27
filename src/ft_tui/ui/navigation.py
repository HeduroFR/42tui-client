"""Main navigation keeps Settings at the trailing edge when space permits."""

from textual.widgets import TabbedContent, Tabs, Tab


class MainTabbedContent(TabbedContent):
    async def on_mount(self):
        from ft_tui.features.clubs.views.workspace import ClubsGlobalControls
        tabs = self.query_one(Tabs)
        await tabs.query_one('#tabs-list').mount(
            ClubsGlobalControls(), before=tabs.get_content_tab('settings'),
        )
        self.call_after_refresh(self.align_settings)

    def on_resize(self):
        self.call_after_refresh(self.align_settings)

    def align_settings(self):
        tabs = self.query_one(Tabs)
        from ft_tui.features.clubs.views.workspace import ClubsGlobalControls
        controls = tabs.query_one(ClubsGlobalControls)
        visible = [tab for tab in tabs.query(Tab) if tab.display]
        available = tabs.query_one('#tabs-scroll').content_size.width
        # On narrow terminals leave the native horizontal tab scrolling intact.
        gap = max(0, available - sum(tab.region.width for tab in visible) - controls.region.width)
        if controls.styles.margin.left != gap:
            controls.styles.margin = (0, 0, 0, gap)
