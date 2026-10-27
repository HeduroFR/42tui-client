"""Common selector behavior for every screen."""

from rich.text import Text
from textual.widgets import Select as TextualSelect
from textual.widgets._select import SelectCurrent


class AppSelect(TextualSelect):
    """Offer only visible choices, with a prompt while options are unavailable."""

    def __init__(self, options, **kwargs):
        self._empty_selection_allowed = kwargs.pop(
            "allow_blank", kwargs.get("value", self.NULL) is self.NULL
        )
        super().__init__(options, **kwargs)

    def _setup_variables_for_options(self, options):
        options = [
            (label, value)
            for label, value in options
            if label is not None
            and (label.plain if isinstance(label, Text) else str(label)).strip()
            and value is not None
            and value is not self.NULL
            and (not isinstance(value, str) or value.strip())
        ]
        # Textual needs a null state for asynchronously populated selectors.
        # As soon as real choices exist, remove its synthetic blank option.
        self._allow_blank = self._empty_selection_allowed or not options
        super()._setup_variables_for_options(options)
        self._options = [(label, value) for label, value in self._options if value is not self.NULL]

    def _watch_prompt(self, prompt: str) -> None:
        # Textual assumes option zero is a synthetic blank when blanks are
        # allowed. Our options omit that row, even while awaiting API data.
        allow_blank = self._allow_blank
        self._allow_blank = False
        try:
            super()._watch_prompt(prompt)
            if self.is_mounted and self.value is self.NULL:
                self.query_one(SelectCurrent).update(self.NULL)
        finally:
            self._allow_blank = allow_blank


Select = AppSelect
