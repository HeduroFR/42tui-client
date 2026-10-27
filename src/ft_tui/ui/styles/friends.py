"""Friends screen styles."""

FRIENDS_CSS = r"""
    #friends-workspace { height: 1fr; padding: 0 1; }
    FriendsWorkspace .friends--self { color: $accent; text-style: bold; }
    #friends-toolbar { height: auto; }
    FriendsWorkspace #friend-suggestions { height: auto; max-height: 10; border: round $primary; background: $surface; }
    FriendsWorkspace #friend-suggestions-status { height: auto; max-height: 3; color: $text-muted; }
    FriendsWorkspace #friend-suggestions-table { height: 6; scrollbar-size-horizontal: 1; }
    #friends-heading { height: auto; }
    #friends-search-row { height: 3; layout: grid; grid-size: 3; grid-columns: 1fr 20 22; grid-rows: 3; grid-gutter: 0 2; margin-bottom: 1; }
    #friends-actions-row { height: 3; layout: grid; grid-size: 5; grid-columns: 20 16 6 6 16; grid-rows: 3; grid-gutter: 1 2; }
    #friends-heading Button { width: 1fr; min-width: 0; padding: 0 1; margin: 0; text-wrap: nowrap; }
    #friends-heading #friends-pokes, #friends-heading #friends-refresh { padding: 0; }
    #friends-heading #social-toggle.has-pending, #friends-heading #friends-pokes.has-pending { color: $accent; text-style: bold; }
    #friends-heading #social-toggle.-primary { color: $text-primary; }
    #friends-search { width: 1fr; min-width: 0; border: solid $border-blurred; }
    #friends-search:focus { border: solid $border; }
    #friends-filter { width: 1fr; }
    #friends-ranking-metric { width: 1fr; display: none; }
    #friends-sync-status { height: auto; max-height: 3; color: $text-muted; margin-top: 1; }
    #friends-sync-progress { width: 100%; height: 1; margin-top: 1; }
    #friends-sync-progress Bar { width: 1fr; }
    #friends-columns { height: 1fr; margin-top: 1; }
    #friends-browser { width: 55%; border: round $primary; padding: 0 1; }
    #friends-workspace.ranking-overview #friends-browser { width: 1fr; }
    #friend-details { width: 45%; border: round $primary; padding: 0 1; }
    #friends-workspace.narrow #friends-browser, #friends-workspace.narrow #friend-details { width: 1fr; }
    #friends-workspace.narrow.previewing #friends-columns { layout: vertical; }
    #friends-workspace.narrow.previewing #friends-browser { height: 7; }
    #friends-workspace.narrow.previewing #friend-details { height: 1fr; }
    #friends-table, #friend-projects { height: 1fr; scrollbar-size-horizontal: 1; }
    #friends-empty { height: auto; color: $text-muted; }
    #friend-details-actions { height: 3; layout: grid; grid-size: 5; grid-rows: 3; grid-gutter: 1 1; }
    #friend-details-actions Button { width: 1fr; min-width: 0; margin: 0; padding: 0 1; text-wrap: nowrap; }
    #friend-details-actions .icon-button { padding: 0; }
    #friend-project-heading { height: 3; margin-top: 1; }
    #friend-project-caption { width: 1fr; height: 3; content-align: left middle; }
    #friend-project-access { width: auto; min-width: 0; margin-left: 1; padding: 0 1; }
    #friend-profile-scroll { height: auto; max-height: 12; margin: 1 0; }
    #friend-profile-scroll.expanded { height: 1fr; max-height: 100%; }
    #friend-profile, #friend-comparison { height: auto; }
    #friend-comparison { margin-top: 1; }
    #friend-project-caption { color: $text-muted; }
"""
