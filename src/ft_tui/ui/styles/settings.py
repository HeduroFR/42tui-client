"""Category navigation and responsive settings workspace."""

SETTINGS_CSS = r"""
    #settings-workspace { width: 1fr; height: 1fr; padding: 1 0 0 0; align: left top; }
    #settings-heading { height: 1; text-style: bold; color: $accent; }
    #settings-intro { height: auto; color: $text-muted; margin-bottom: 1; }
    #settings-body { height: 1fr; }
    #settings-sidebar {
        width: 23; height: 1fr; padding: 1;
        border-right: solid $primary; background: $surface;
    }
    #settings-categories { height: 1fr; background: transparent; }
    #settings-categories ListItem { height: 3; padding: 1; }
    #settings-categories ListItem.-highlight { background: $primary 25%; color: $text; }
    #settings-categories:focus ListItem.-highlight { background: $primary 45%; text-style: bold; }
    #settings-content { width: 1fr; height: 1fr; padding: 0 1; align: left top; }
    .settings-panel { width: 1fr; height: auto; }
    .settings-section, #provider-card {
        width: 1fr; height: auto; padding: 1 2;
        border: round $primary; background: $surface; margin-bottom: 1;
    }
    .section-kicker { height: auto; color: $accent; text-style: bold; margin-bottom: 1; }
    .settings-label { height: auto; margin-top: 1; color: $text; text-style: bold; }
    .field-help { height: auto; color: $text-muted; }
    #settings-actions { height: 3; margin-top: 1; }
    #save-settings { width: auto; min-width: 0; margin-right: 1; }
    #settings-status { width: 1fr; height: 3; content-align: left middle; color: $text-muted; }
    #settings-help { height: auto; color: $text-muted; margin-top: 1; }
    #provider-title { height: auto; text-style: bold; margin-bottom: 1; }
    #settings-workspace.compact { padding: 0; }
    .compact #settings-sidebar { width: 18; padding: 0 1; }
    .compact #settings-content { padding: 0 1; }
    .compact .settings-section, .compact #provider-card { padding: 0 1 1 1; }
    .compact #settings-categories ListItem { padding: 1 0; }
"""
