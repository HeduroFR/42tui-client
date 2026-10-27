"""Projects screen styles."""

PROJECTS_CSS = r"""#workspace { height: 1fr; }
    #project-list { width: 36%; min-width: 25; border: round $primary; padding: 0 1; }
    #project-details { width: 64%; border: round $primary; padding: 0 1; }
    #project-list-header { height: 2; }
    #project-count { width: 1fr; text-align: right; color: $text-muted; }
    #project-filters { height: auto; margin-bottom: 1; }
    #project-filters > Select { width: 1fr; min-width: 0; }
    #project-view { margin-right: 1; }
    #project-search { margin-bottom: 1; }
    #project-list-view { height: 1fr; border: none; padding: 0; background: transparent; }
    .project-rank-header { height: 2; min-height: 2; padding: 0 1; border-top: solid $secondary; color: $accent; text-style: bold; }
    .project-rank-header.-highlight { background: $primary 20%; }
    .rank-header-content { height: 1; width: 1fr; }
    .rank-header-label { width: 1fr; }
    .rank-header-progress { width: auto; text-align: right; }
    .project-entry { height: 3; min-height: 3; padding: 0 1 1 1; border: none; background: transparent; }
    .project-entry-content { width: 1fr; height: 2; }
    .project-entry.exam-entry { height: 4; min-height: 4; padding-left: 0; }
    .project-entry.exam-entry > .project-entry-content { height: 3; border-left: wide $accent; background: $accent 8%; }
    .project-exam-badge { display: none; height: 1; color: $accent; text-style: bold; }
    .exam-entry .project-exam-badge { display: block; }
    #project-list-view > .project-entry.-hovered > .project-entry-content { background: #333333; }
    #project-list-view > .project-entry.-highlight > .project-entry-content { background: $primary 20%; }
    .project-entry.-highlight .project-name { text-style: bold; }
    .project-name { width: 1fr; text-style: bold; }
    .project-entry-meta { height: 1; }
    .project-state { text-style: bold; width: auto; }
    .project-local-state { width: auto; margin-left: 1; color: $text-muted; }
    .project-score { width: 1fr; text-align: right; color: $success; text-style: bold; }
    .state-active { color: $accent; }
    .state-done { color: $success; }
    .state-available { color: $warning; }
    .state-failed { color: $error; }
    .state-inactive { color: $text-muted; }
    .state-locked { color: $text-muted; }
    #project-empty { display: none; color: $text-muted; padding: 1; }
    .panel-title { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #project-heading-row { height: auto; min-height: 3; }
    #project-heading { width: 1fr; height: auto; margin: 1 1 0 0; }
    #show-project-testers { width: auto; min-width: 0; }
    #project-summary { height: auto; color: $text-muted; margin-bottom: 1; }
    #project-details-scroll { height: 1fr; }
    #project-details-columns { height: auto; min-height: 17; }
    #project-overview { width: 3fr; height: auto; padding-right: 2; }
    #project-workspace { width: 2fr; height: auto; border-left: solid $secondary; padding-left: 2; }
    #project-details-columns.stacked { layout: vertical; }
    #project-details-columns.stacked > #project-overview { width: 1fr; padding-right: 0; margin-bottom: 1; }
    #project-details-columns.stacked > #project-workspace { width: 1fr; border-left: none; border-top: solid $secondary; padding: 1 0 0 0; }
    #project-registration { height: auto; margin-top: 1; border-top: solid $secondary; padding-top: 1; }
    #registration-relationship, #registration-feedback { height: auto; }
    #registration-relationship { text-style: bold; }
    #registration-feedback { color: $warning; }
    #project-registration Button { width: 1fr; min-width: 0; height: 3; margin-top: 1; }
    #registration-actions { height: 4; }
    #registration-actions #registration-action { margin: 1 2 0 0; }
    #show-project-activity { width: 1fr; min-width: 0; height: 3; margin-top: 1; }
    #details-content { height: auto; }
    #project-subject-status { height: auto; color: $text-muted; }
    #project-workspace-status { height: auto; margin: 1 0; }
    #project-actions, #project-workspace-actions { height: 3; }
    #project-actions Button, #project-workspace-actions Button { width: auto; min-width: 0; margin-right: 1; }
    #project-time-spent { height: 1; color: $accent; text-style: bold; margin-top: 1; }
    #project-timer-status { height: auto; color: $text-muted; }
    #project-timer-toggle { width: auto; min-width: 0; margin-top: 1; }
    #project-notes-header { height: 3; margin-top: 1; }
    #notes-title { width: 1fr; height: 3; content-align: left middle; text-style: bold; color: $accent; }
    #new-project-note { width: auto; }
    #project-notes-list, #project-notes-empty { height: 1fr; min-height: 8; border: round $secondary; padding: 0 1; }
    #project-notes-list { display: none; }
    #project-notes-empty { color: $text-muted; }
    .project-note-entry { height: 3; padding: 0 1; }
    .project-note-entry.-hovered { background: #333333; }
    .project-note-entry.-highlight { background: $primary 20%; }
    #project-details-help { height: auto; color: $text-muted; margin-top: 1; }
    """
