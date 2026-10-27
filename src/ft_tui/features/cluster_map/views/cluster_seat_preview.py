"""A cached, non-modal enlargement of the seat under the pointer."""
from rich.text import Text
from ft_tui.features.cluster_map.state import session_label, status_label
from textual.containers import Vertical
from ft_tui.ui.components import Static
from ft_tui.i18n import translate
from ft_tui.features.cluster_map.views.portrait import ClusterPortrait


class ClusterSeatPreview(Vertical):
    def __init__(self):
        super().__init__(id='cluster-seat-preview')
        self.hostname=None
        self.seat=None

    def compose(self):
        yield ClusterPortrait(cover=True,classes='cluster-preview-photo')
        yield Static('',classes='cluster-preview-details',markup=False,localize=False)

    def on_mount(self):
        self.set_interval(1,self._render_details)

    def update_seat(self,seat,image):
        self.seat=seat
        self.hostname=seat.hostname
        portrait=self.query_one(ClusterPortrait)
        portrait.display=bool(seat.login)
        portrait.set_blurred(seat.session=='locked')
        portrait.set_badges(bool(seat.open_count),seat.friend)
        portrait.image=image if seat.login else None
        portrait.status='unavailable' if seat.login else None
        self._render_details()

    def _details(self,seat):
        t=lambda value:translate(value,getattr(self.app,'language','en'))
        reports=t('Reports unavailable') if seat.open_count is None else t('{count} open reports').format(count=seat.open_count)
        details=Text(seat.login or t('No active login'),style='bold')
        details.append('\n'+seat.hostname+(' · '+t('Friend') if seat.friend else ''))
        details.append('\n'+status_label(seat.machine,t)+' · '+status_label(seat.session,t))
        if seat.session=='locked' and seat.lock_time:
            details.append('\n'+session_label(seat,t))
        details.append('\n'+reports)
        return details

    def height_for_seat(self,seat,width):
        if seat.login:return 16
        # Border and horizontal padding leave four columns outside the text.
        return 2+max(4,len(self._details(seat).wrap(self.app.console,max(1,width-4))))

    def _render_details(self):
        if not self.display or self.seat is None:return
        details=self._details(self.seat)
        widget=self.query_one('.cluster-preview-details',Static)
        height=max(4,len(details.wrap(self.app.console,max(1,self.content_size.width or 22))))
        widget.styles.height=widget.styles.min_height=height
        widget.update(details)
