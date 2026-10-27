"""Dashboard screen styles."""

DASHBOARD_CSS = r"""#dashboard-page { height: 1fr; overflow-y: auto; padding: 0 1; }
    #dashboard-heading { height: 2; }
    #dashboard-title { width: 1fr; color: $accent; text-style: bold; }
    #dashboard-subtitle { width: auto; color: $text-muted; content-align: right middle; }
    #dashboard-cards { height: 13; min-height: 13; }
    #dashboard-action-cards { height: 14; min-height: 14; margin-top: 1; }
    #dashboard-action-cards .dashboard-card { padding: 1 2; }
    #dashboard-action-cards .dashboard-kicker { margin-bottom: 1; }
    #dashboard-profile-data { height: 1fr; }
    #dashboard-profile-card .dashboard-kicker { height: 1; }
    #dashboard-identity { height: 4; }
    #dashboard-portrait { width: 8; height: 4; margin-right: 2; background: $boost; }
    #dashboard-identity-text { width: 1fr; height: 4; align-vertical: middle; }
    #dashboard-login { height: 1; color: $accent; text-style: bold; }
    #dashboard-workstation { height: 1; margin-top: 1; color: $text-muted; }
    #dashboard-balances { height: 2; border-top: solid $secondary; }
    .compact-profile #dashboard-identity { layout: vertical; }
    .compact-profile #dashboard-portrait { width: 6; height: 2; margin-right: 0; }
    .compact-profile #dashboard-identity-text { width: 1fr; height: 2; }
    .compact-profile #dashboard-workstation { margin-top: 0; }
    .dashboard-stat { width: 1fr; height: 1; }
    #dashboard-correction-stat { border-left: solid $secondary; padding-left: 1; }
    .dashboard-stat-value { height: 1; text-style: bold; }
    .dashboard-card {
        width: 1fr; min-width: 16; height: 1fr; margin-right: 1;
        padding: 1 2; border: round $secondary; background: $surface;
    }
    .dashboard-card:last-child { margin-right: 0; }
    .dashboard-kicker { color: $accent; text-style: bold; margin-bottom: 1; }
    #dashboard-continue-name { height: 1; text-style: bold; color: $text; }
    #dashboard-continue-activity { height: 1; color: $text-muted; }
    #dashboard-continue-time-row { height: 1; margin-top: 0; }
    #dashboard-continue-meta { width: auto; color: $accent; text-style: bold; }
    #dashboard-continue-time-label { width: 1fr; text-align: right; color: $text-muted; }
    #dashboard-continue-spacer { height: 1fr; }
    #dashboard-continue-actions { height: 3; min-height: 3; margin-top: 1; }
    #dashboard-continue-actions Button { width: 1fr; margin-right: 1; }
    #dashboard-continue-actions Button:last-child { margin-right: 0; }
    #dashboard-recent-notes { height: 1fr; border: none; padding: 0; background: transparent; }
    .dashboard-note-entry { height: 3; padding: 0 1; }
    .dashboard-note-entry.-hovered { background: #333333; }
    .dashboard-note-entry.-highlight { background: $primary 20%; }
    .dashboard-note-title { text-style: bold; }
    .dashboard-note-meta { color: $text-muted; }
    #dashboard-notes-empty { color: $text-muted; }
    #dashboard-needs-summary { height: 1; text-style: bold; }
    #dashboard-needs-list { height: 2; color: $text-muted; }
    #dashboard-needs-spacer { height: 1fr; }
    #dashboard-setup-next { height: 3; min-height: 3; margin-top: 1; }
    #dashboard-activity-card { width: 1fr; padding: 1 1 0 1; }
    #dashboard-activity-heatmap { height: 5; content-align: center middle; }
    #dashboard-cluster-card { content-align: center middle; }
    #dashboard-cluster-card .dashboard-kicker { margin-bottom: 0; }
    #dashboard-cluster-map { width: 1fr; height: 3; min-height: 3; }
    #dashboard-cluster-status {
        width: 1fr; height: 1fr; content-align: center middle;
        color: $accent; text-style: bold;
    }
    #dashboard-blackhole-card { width: 1.4fr; margin-right: 0; padding: 0 1; }
    #dashboard-blackhole-card .dashboard-kicker { margin-top: 1; margin-bottom: 1; }
    #dashboard-goals-status {
        height: auto; max-height: 2; color: $warning;
    }
    #dashboard-deadlines { height: 1fr; align-vertical: middle; }
    #dashboard-deadline-summary {
        height: 3; border-top: solid $secondary; color: $text;
    }
    #dashboard-blackhole-days {
        width: 1fr; height: 1fr; padding-right: 1;
        color: $text; content-align: left top;
    }
    #dashboard-blackhole-days.approaching { color: $warning; }
    #dashboard-blackhole-days.urgent { color: $error; }
    #dashboard-blackhole-date {
        width: 1fr; height: 1fr; border-left: solid $secondary; padding-left: 1;
        color: $text; content-align: left top;
    }
    #dashboard-progress-card {
        width: 1fr; height: auto; min-height: 8; margin-top: 1;
        margin-right: 0; padding: 0 2; border: round $primary;
        background: $surface;
    }
    #dashboard-progress-topline { height: 1; }
    #dashboard-progress-topline .dashboard-kicker { width: 1fr; margin: 0; }
    #dashboard-progress-context { width: auto; color: $text-muted; }
    #dashboard-progress-heading { height: 1; margin-top: 0; }
    #dashboard-progress-value { width: auto; color: $accent; text-style: bold; }
    #dashboard-progress-caption { width: 1fr; color: $text-muted; padding-left: 2; content-align: left middle; }
    #dashboard-progress-bar { height: 2; margin: 1 0; }
    #dashboard-progress-legend { height: 1; margin-top: 0; }
    .dashboard-progress-stat { width: 1fr; color: $text-muted; }
    .dashboard-progress-stat:last-child { width: auto; }
    #dashboard-progress-next { height: 1; margin-top: 0; padding: 0 1; background: $boost; }
    #dashboard-progress-next-label { width: auto; color: $text-muted; }
    #dashboard-progress-next-name { width: 1fr; padding-left: 2; color: $text; text-style: bold; }
    """
