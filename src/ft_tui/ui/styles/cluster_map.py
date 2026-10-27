"""Compact maps and workstation overlays use shared app theme colors."""

CLUSTER_MAP_CSS = r"""
ClusterMapWorkspace { height: 1fr; min-height: 0; overflow: hidden hidden; }
#cluster-body { height: 1fr; min-height: 0; layout: horizontal; }
#cluster-map-panel { height: 1fr; min-height: 0; width: 1fr; }
#cluster-menu-actions { width: 13; height: 3; }
ClusterMapWorkspace #cluster-toolbar {
    layout: vertical; width: 26; min-width: 26; height: 1fr; min-height: 0;
    padding: 0 1; margin-right: 1; border-right: solid $primary 25%;
}
ClusterMapWorkspace .cluster-menu-label { display: block; height: auto; }
ClusterMapWorkspace #cluster-menu-title { color: $accent; text-style: bold; margin-bottom: 1; }
ClusterMapWorkspace .cluster-menu-caption { color: $text-muted; margin-top: 1; height: 1; }
ClusterMapWorkspace #cluster-toolbar AppSelect,
ClusterMapWorkspace #cluster-toolbar Input { width: 100%; min-width: 0; height: 3; }
#cluster-toolbar Input { border: solid $border-blurred; padding: 0 1; }
#cluster-toolbar Input:focus { border: solid $border; }
#cluster-toolbar AppSelect > SelectCurrent { padding: 0 1; height: 3; border: solid $border-blurred; }
#cluster-toolbar AppSelect:focus > SelectCurrent { border: solid $border; }
#cluster-toolbar AppSelect > SelectCurrent #label { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }
ClusterMapWorkspace #cluster-menu-actions { width: 100%; margin-top: 1; }
ClusterMapWorkspace #cluster-friends { width: 1fr; min-width: 0; height: 3; padding: 0; text-wrap: nowrap; }
ClusterMapWorkspace #cluster-menu-hints { color: $text-muted; margin-top: 1; }
ClusterMapWorkspace.short-sidebar .cluster-menu-label { display: none; }
ClusterMapWorkspace.short-sidebar #cluster-menu-actions { margin-top: 0; }
#cluster-view { layout: grid; grid-size: 2 2; grid-columns: 1fr 1fr; grid-rows: 3 3; grid-gutter: 1 2; height: 7; width: 100%; }
ClusterMapWorkspace .cluster-view-button { width: 100%; min-width: 0; height: 3; padding: 0; background: $surface; color: $text-muted; }
ClusterMapWorkspace .cluster-view-button:blur { border: blank; }
ClusterMapWorkspace .cluster-view-button:hover { background: $accent 8%; color: $text; }
ClusterMapWorkspace .cluster-view-button.selected { background: $accent 12%; color: $accent; text-style: bold; }
ClusterMapGrid .cluster--low { color: #22c55e; }
ClusterMapGrid .cluster--medium { color: #eab308; }
ClusterMapGrid .cluster--high { color: #ef4444; }
ClusterMapGrid .cluster--border { color: $text-muted 45%; }
#cluster-filter { width: 17; min-width: 9; }
#cluster-search { width: 1fr; min-width: 8; }
#cluster-friends { width: 8; min-width: 6; }
#cluster-refresh { width: 5; min-width: 3; margin-left: 1; }
#cluster-freshness { height: auto; margin-top: 1; color: $text-muted; }
#cluster-focus { height: 1; color: $text-muted; }
#cluster-grid { layers: seats preview; height: 1fr; min-height: 0; padding: 0; overflow: hidden hidden; }
.cluster-seat-portrait { layer: seats; }
#cluster-seat-preview {
    position: absolute; layer: preview; width: 26; height: 16;
    background: $surface; border: round $accent; padding: 0 1;
    overflow: hidden hidden;
}
#cluster-seat-preview .cluster-preview-photo { width: 100%; height: 1fr; min-height: 1; }
#cluster-seat-preview .cluster-preview-details { height: 4; min-height: 4; }
ClusterMapGrid .cluster--free { color: $text-muted; background: $surface 15%; }
ClusterMapGrid .cluster--occupied { color: $text; background: $surface 65%; }
ClusterMapGrid .cluster--offline { color: $error; background: $error 12%; text-style: bold; }
ClusterMapGrid .cluster--unknown { color: $text-muted; background: $background; }
ClusterMapGrid .cluster--friend { color: $accent; background: $accent 20%; text-style: bold; }
ClusterMapGrid .cluster--focused { color: $accent; background: $accent 20%; text-style: bold; }
ClusterMapGrid .cluster--issue { color: $warning; }
ClusterWorkstationModal { align: center middle; padding: 0; background: $background 65%; }
#cluster-dialog { width: 132; max-width: 96%; height: 40; max-height: 92%; border: round $primary; background: $surface; padding: 0 1; }
#cluster-modal-header { height: 3; min-height: 3; align-horizontal: right; }
#cluster-close { height: 3; }
#cluster-occupant-notice { height: auto; color: $warning; }
#cluster-modal-tabs { height: 1fr; min-height: 5; }
#cluster-modal-tabs TabPane { padding: 0; }
.cluster-modal-scroll { height: 1fr; }
#cluster-person-row { height: 1fr; min-height: 0; }
#cluster-person-photo { width: 36%; height: 1fr; align: center middle; margin-right: 3; padding: 0 1; }
#cluster-person-photo ClusterPortrait { width: 100%; height: 18; max-height: 70%; border: round $primary 60%; background: $background; }
#cluster-portrait-name { height: auto; text-align: center; text-style: bold; margin-top: 1; }
#cluster-portrait-seat { height: auto; text-align: center; color: $text-muted; margin-top: 1; }
#cluster-person-details { width: 1fr; height: 1fr; }
#cluster-person-heading { height: auto; min-height: 4; border-bottom: solid $primary 25%; margin-bottom: 1; }
#cluster-person-info { width: 1fr; height: auto; text-style: bold; }
.cluster-detail-card { height: auto; border: round $primary 25%; padding: 0 1; margin-bottom: 1; }
.cluster-detail-card Static { height: auto; }
.cluster-detail-title { color: $text-muted; text-style: bold; }
#cluster-person-cards { layout: grid; grid-size: 3 1; grid-rows: auto; grid-columns: 1fr 1fr 1fr; grid-gutter: 0 1; height: auto; margin-bottom: 1; }
#cluster-person-cards > .cluster-detail-card { width: 100%; height: 100%; margin: 0; }
#cluster-person-cards > .cluster-detail-card:last-child { margin-right: 0; }
#cluster-person-actions { width: auto; height: 3; }
#cluster-person-actions Button { min-width: 10; padding: 0 1; }
#cluster-level-progress { width: 100%; height: 1; margin-top: 0; }
#cluster-level-progress Bar { width: 1fr; }
#cluster-level-progress PercentageStatus { width: 5; }
#cluster-next-level { margin: 1 0 0 0; }
ClusterWorkstationModal.compact-person #cluster-person-row { layout: vertical; }
ClusterWorkstationModal.compact-person #cluster-person-heading { layout: vertical; }
ClusterWorkstationModal.compact-person #cluster-person-info { width: 100%; }
ClusterWorkstationModal.compact-person #cluster-person-cards { layout: vertical; }
ClusterWorkstationModal.compact-person #cluster-person-cards > .cluster-detail-card { width: 100%; height: auto; margin-right: 0; }
ClusterWorkstationModal.compact-person #cluster-person-photo { width: 100%; height: 11; margin: 0 0 1 0; }
ClusterWorkstationModal.compact-person #cluster-person-photo ClusterPortrait { width: 18; height: 6; }
ClusterWorkstationModal.compact-person #cluster-portrait-name,
ClusterWorkstationModal.compact-person #cluster-portrait-seat { margin-top: 0; }
ClusterWorkstationModal.compact-person #cluster-person-details { width: 100%; height: 1fr; }
.cluster-modal-actions { height: 3; }
.cluster-modal-actions Button { width: auto; margin-right: 1; }
#cluster-reports { height: auto; }
#cluster-report-status { height: auto; color: $text-muted; }
.cluster-report-body { height: auto; }
#cluster-resolved { height: 3; }
.cluster-section-heading { height: auto; border-bottom: solid $primary 25%; margin-bottom: 1; padding-bottom: 1; }
.cluster-section-heading Static { height: auto; }
.cluster-section-name { text-style: bold; }
#cluster-workstation-layout { height: auto; }
#cluster-workstation-overview { width: 30%; height: auto; margin-right: 1; padding: 0 1; }
#cluster-workstation-details { width: 1fr; height: auto; }
#cluster-storage-title { margin-left: 2; }
#cluster-issues-section { height: auto; margin-left: 1; }
#cluster-issues-title, #cluster-count-caption, #cluster-report-status { margin-left: 1; }
.cluster-host-name { text-style: bold; color: $accent; }
#cluster-machine-status { text-style: bold; }
.machine-online { color: $success; }
.machine-offline { color: $error; }
.machine-unknown { color: $text-muted; }
.cluster-host-location { margin: 1 0; border-top: solid $primary 20%; }
.has-issues #cluster-machine-reports { color: $warning; }
#cluster-machine-session { padding: 0; }
.cluster-storage-value { text-style: bold; }
.storage-warning Bar > .bar--bar, .storage-warning Bar > .bar--complete { color: $warning; }
.storage-critical Bar > .bar--bar, .storage-critical Bar > .bar--complete { color: $error; }
.cluster-count-card { padding: 0 1; border: none; }
.cluster-count-value { text-style: bold; }
.status-open { border-left: thick $warning; }
.status-in_progress { border-left: thick $accent; }
.status-resolved { border-left: thick $success; }
.cluster-section-caption { height: auto; color: $text-muted; }
#cluster-issues-title { width: 1fr; height: auto; text-style: bold; }
#cluster-issues-heading { align-vertical: middle; padding: 0; margin-bottom: 0; }
#cluster-report-status { margin-bottom: 1; }
.cluster-summary-cards, .cluster-storage-cards {
    layout: grid; grid-size: 3 1; grid-rows: auto; grid-columns: 1fr 1fr 1fr;
    grid-gutter: 0 1; height: auto; margin-bottom: 1;
}
.cluster-storage-cards { grid-size: 2 1; grid-columns: 1fr 1fr; }
.cluster-summary-cards > .cluster-detail-card,
.cluster-storage-cards > .cluster-detail-card { width: 100%; height: 100%; margin: 0; }
.cluster-storage-progress { width: 100%; height: 1; margin-top: 1; }
.cluster-storage-progress Bar { width: 1fr; }
.cluster-storage-progress PercentageStatus { width: 5; }
.cluster-report-card { height: auto; border: round $primary 25%; padding: 0 1; margin: 0; background: $surface; }
.cluster-report-card.status-open { border-left: thick $warning; }
.cluster-report-card.status-in_progress { border-left: thick $accent; }
.cluster-report-card.status-resolved { border-left: thick $success; }
.cluster-report-meta { height: auto; color: $text-muted; padding: 0 1; }
.cluster-report-card Collapsible { border: none; padding: 0; background: transparent; }
.cluster-report-card Collapsible > Contents { padding: 1 1 0 1; }
.cluster-report-body { margin-bottom: 1; }
ClusterWorkstationModal.compact-person #cluster-workstation-layout { layout: vertical; }
ClusterWorkstationModal.compact-person #cluster-workstation-overview { width: 100%; margin-right: 0; }
ClusterWorkstationModal.compact-person #cluster-workstation-details { width: 100%; }
ClusterWorkstationModal.compact-person .cluster-summary-cards,
ClusterWorkstationModal.compact-person .cluster-storage-cards { layout: vertical; }
ClusterWorkstationModal.compact-person .cluster-summary-cards > .cluster-detail-card,
ClusterWorkstationModal.compact-person .cluster-storage-cards > .cluster-detail-card { height: auto; margin-bottom: 1; }
ClusterWorkstationModal.compact-person #cluster-issue-counts { layout: grid; }
ClusterWorkstationModal.compact-person #cluster-issue-counts > .cluster-detail-card { height: 100%; margin-bottom: 0; padding: 0 1; }
ClusterWorkstationModal.compact-person #cluster-issues-heading { layout: vertical; }
ClusterWorkstationModal.compact-person #cluster-issues-title { width: 100%; }
"""
