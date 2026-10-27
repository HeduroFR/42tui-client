"""Theme-aware styles for the read-only student profile."""
PROFILE_CSS = '''
UserProfileScreen { background: $surface; padding: 1 2; }
#profile-controls { height: 3; margin-bottom: 1; }
#profile-controls Button { width: auto; min-width: 8; margin-right: 1; }
#profile-control-spacer { width: 1fr; }
#profile-status { height: auto; color: $text-muted; margin-bottom: 1; }
#profile-scroll { height: 1fr; }
#profile-identity { height: auto; min-height: 8; margin-bottom: 1; }
#profile-portrait { width: 18; height: 8; margin-right: 2; }
#profile-heading { width: 1fr; height: auto; }
#profile-name { height: auto; text-style: bold; color: $accent; }
#profile-login, #profile-coalition, #profile-contact, #profile-titles { height: auto; margin-top: 1; }
#profile-cursus-row { height: 3; margin-bottom: 1; }
#profile-cursus-label { width: auto; padding: 1 2 0 0; }
#profile-cursus { width: 1fr; }
#profile-stats { height: auto; margin-bottom: 1; }
.profile-stat { width: 1fr; height: auto; min-height: 5; border-left: thick $primary; padding: 0 1; }
.profile-caption { height: auto; color: $text-muted; }
.profile-value { height: auto; text-style: bold; }
#profile-level-caption { height: auto; text-style: bold; }
#profile-level { width: 1fr; height: 1; margin: 0 0 1 0; }
#profile-level Bar { width: 1fr; }
#profile-overview { height: auto; margin-bottom: 1; }
.profile-panel { width: 1fr; height: auto; min-height: 9; border: round $primary; padding: 1; margin-right: 1; }
.profile-section-title { height: auto; text-style: bold; color: $accent; margin-bottom: 1; }
#profile-weeks, #profile-presence, #profile-goals, #profile-piscine { height: auto; }
#profile-calendar-panel { height: auto; border: round $primary; padding: 1; margin-bottom: 1; }
#profile-calendar { height: auto; }
#profile-tabs { height: auto; min-height: 16; }
#profile-tabs ContentSwitcher, #profile-tabs TabPane { height: auto; }
#profile-project-tools { height: 3; margin-bottom: 1; }
#profile-project-status { height: auto; color: $text-muted; margin-bottom: 1; }
#profile-projects { height: 14; }
#profile-achievements { height: auto; }
.profile-achievement { height: auto; padding: 0 1 1 1; }
UserProfileScreen.compact #profile-overview { layout: vertical; }
UserProfileScreen.compact .profile-panel { width: 1fr; min-height: 0; margin: 0 0 1 0; }
UserProfileScreen.tiny { padding: 0 1; }
UserProfileScreen.tiny #profile-portrait { width: 10; height: 6; margin-right: 1; }
UserProfileScreen.tiny #profile-stats { layout: grid; grid-size: 2; grid-gutter: 1; }
UserProfileScreen.tiny .profile-stat { width: 1fr; }
UserProfileScreen.tiny #profile-controls Button { min-width: 0; padding: 0 1; margin-right: 0; }
'''
