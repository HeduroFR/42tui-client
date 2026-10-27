"""Compatibility accessors while feature state moves out of the Textual shell."""


class StateField:
    """Forward a legacy shell attribute without keeping a second copy of state."""

    def __init__(self, owner: str, field: str):
        self.owner = owner
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return getattr(getattr(instance, self.owner), self.field)

    def __set__(self, instance, value):
        setattr(getattr(instance, self.owner), self.field, value)
