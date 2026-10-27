"""Authenticated server push with reconnect resync and account-isolated dispatch."""
import threading
from textual.message import Message
from textual.widget import Widget


class PushEvents(Widget):
    DEFAULT_CSS = 'PushEvents { display: none; }'

    class Changed(Message):
        def __init__(self, context, topic):
            super().__init__()
            self.context, self.topic = context, topic

    def __init__(self):
        super().__init__(id='push-events')
        self.context = None
        self.stop = None
        self.pending = set()
        self.dispatching = False

    def scope(self):
        return (getattr(self.app, 'account_generation', None), getattr(self.app, 'account_id', None),
                id(getattr(self.app, 'provider', None)), getattr(self.app, 'account_connected', False))

    def on_mount(self):
        self.set_interval(1, self.check_context)
        self.check_context()

    def on_unmount(self):
        if self.stop:
            self.stop.set()

    def check_context(self):
        context = self.scope()
        if context == self.context:
            return
        if self.stop:
            self.stop.set()
        self.context = context
        self.pending.clear()
        provider = getattr(self.app, 'provider', None)
        if not context[1] or not context[3] or not callable(getattr(provider, 'event_stream', None)):
            return
        stop = self.stop = threading.Event()

        def listen():
            delay = 1
            while not stop.is_set():
                try:
                    for topic in provider.event_stream(stop):
                        if stop.is_set():
                            return
                        delay = 1
                        self.post_message(self.Changed(context, topic))
                except Exception:
                    if not stop.is_set():
                        self.post_message(self.Changed(context, 'disconnected'))
                if stop.wait(delay):
                    return
                delay = min(30, delay * 2)
        threading.Thread(target=listen, name='42tui-push', daemon=True).start()

    def on_push_events_changed(self, event):
        event.stop()
        if event.context != self.scope():
            return
        if event.topic == 'disconnected':
            for status in self.app.query('#social-status, #clubs-status'):
                status.update('Live updates disconnected. Reconnecting…')
            return
        self.pending.update(('clubs', 'social') if event.topic == 'resync' else (event.topic,))
        if not self.dispatching:
            self.dispatching = True
            self.run_worker(self.dispatch(event.context), group='push-dispatch')

    async def dispatch(self, context):
        from ft_tui.features.clubs.views.workspace import ClubsWorkspace
        from ft_tui.features.social.views.inbox import SocialInbox
        try:
            while self.pending and context == self.scope():
                topics, self.pending = self.pending, set()
                if 'clubs' in topics:
                    topics.add('social')  # Global DND changes affect both inboxes.
                    for clubs in self.app.query(ClubsWorkspace):
                        if clubs.connected():
                            await clubs.poll()
                            await clubs.reload()
                if 'social' in topics:
                    for inbox in self.app.query(SocialInbox):
                        await inbox.sync()
        finally:
            self.dispatching = False
            if self.pending and self.is_mounted:
                # A scope switch during an awaited refresh must not swallow the
                # new stream's initial resync.
                self.post_message(self.Changed(self.scope(), 'resync'))
