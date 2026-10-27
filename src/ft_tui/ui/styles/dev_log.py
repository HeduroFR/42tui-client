"""Dev Log screen styles."""

DEV_LOG_CSS = r"""#dev-log-workspace { height: 1fr; }
    #dev-log-sidebar { width: 30%; min-width: 24; border: round $primary; padding: 0 1; }
    #dev-log-main { width: 70%; border: round $primary; padding: 0 1; }
    #dev-log-project { margin-bottom: 1; }
    #dev-log-note-list { height: 1fr; border: none; padding: 0; background: transparent; }
    .dev-log-note { height: 3; padding: 0 1; }
    .dev-log-note.-hovered { background: #333333; }
    .dev-log-note.-highlight { background: $primary 20%; }
    .dev-log-note-title { text-style: bold; }
    .dev-log-note-date { color: $text-muted; }
    #dev-log-title { margin-bottom: 1; }
    #dev-log-content { height: 1fr; border: round $secondary; padding: 0 1; }
    #dev-log-editor { height: 1fr; border: none; padding: 0; }
    #dev-log-preview { height: 1fr; overflow-y: auto; padding: 0; display: none; }
    #dev-log-actions { height: 3; align-horizontal: right; margin-top: 1; }
    #dev-log-actions Button { margin-left: 1; }
    #dev-log-status { width: 1fr; color: $text-muted; content-align: left middle; }
    """
