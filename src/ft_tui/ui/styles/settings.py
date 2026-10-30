"""Category navigation and responsive settings workspace."""

SETTINGS_CSS = r"""
    #settings-workspace { width: 1fr; height: 1fr; padding: 0; }
    #settings-topbar { height: 3; padding: 0 1; background: $surface; }
    #settings-heading { width: 1fr; height: 3; content-align: left middle; text-style: bold; color: $accent; }
    #settings-body { height: 1fr; }
    #settings-sidebar { width: 23; height: 1fr; padding: 1; background: $surface; border-right: solid $secondary; }
    #settings-nav-heading { margin: 0 1 1 1; }
    #settings-categories { height: 1fr; background: transparent; border: none; padding: 0; }
    #settings-categories ListItem { height: 3; padding: 1; color: $text-muted; }
    #settings-categories ListItem:hover { background: $primary 15%; color: $text; }
    #settings-categories ListItem.-highlight { background: $primary 25%; color: $text; text-style: bold; }
    #settings-categories:focus ListItem.-highlight { background: $primary 45%; text-style: bold; }
    #settings-content { width: 1fr; height: 1fr; padding: 1 2; align: left top; }
    #settings-category-title { height: 1; color: $text; text-style: bold; }
    #settings-category-description { height: auto; color: $text-muted; margin: 0 0 1 0; }
    .settings-panel { width: 1fr; height: auto; }
    .settings-section, #provider-card {
        width: 1fr; height: auto; padding: 1 2; border-left: tall $secondary;
        background: $surface; margin-bottom: 1;
    }
    .settings-section:focus-within { border-left: tall $primary; }
    .section-kicker { height: auto; color: $accent; text-style: bold; margin-bottom: 1; }
    .settings-label { height: auto; margin-top: 1; color: $text; text-style: bold; }
    .field-help { height: auto; color: $text-muted; }
    #username-gradient-preview, #username-gradient-help { padding-left: 1; }
    #settings-storage-row { height: 3; }
    #settings-storage { width: 1fr; }
    #settings-storage-apply { width: auto; min-width: 0; margin-left: 2; }
    .narrow-storage #settings-storage-row { height: 6; layout: vertical; }
    .narrow-storage #settings-storage-apply { margin-left: 0; }
    #community-links { height: auto; }
    .community-card { width: 1fr; margin-right: 1; }
    .community-card:last-child { margin-right: 0; }
    .community-description { height: auto; color: $text; }
    .community-url { height: auto; color: $text-muted; margin: 1 0; }
    .community-card Button { width: auto; min-width: 0; }
    .compact #community-links { layout: vertical; }
    .compact .community-card { margin-right: 0; }
    #community-status { height: auto; color: $text-muted; }
    #settings-actions { height: 3; padding: 0 1; background: $surface; }
    #save-settings { width: auto; min-width: 0; }
    #settings-status { width: 1fr; height: 3; content-align: left middle; color: $text-muted; }
    #settings-help { height: 1; padding: 0 1; color: $text-muted; }
    #provider-title { height: auto; text-style: bold; margin-bottom: 1; }
    .compact #settings-sidebar { width: 18; padding: 0 1; }
    .compact #settings-content { padding: 0 1; }
    .compact .settings-section, .compact #provider-card { padding: 0 1 1 1; }
    .compact #settings-categories ListItem { padding: 1 0; }
"""
