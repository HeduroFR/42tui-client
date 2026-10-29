"""Interpret tester terminal redraws while retaining bounded scrollback."""
from itertools import groupby
import re

import pyte
from rich.style import Style
from rich.text import Text


class TesterConsole:
    def __init__(self):
        # Match WorkspaceSession's private PTY dimensions.
        self.screen = pyte.HistoryScreen(100, 24, history=1000)
        self.stream = pyte.Stream(self.screen)

    def feed(self, text):
        self.stream.feed(text)

    def render(self):
        screen = self.screen
        rows = list(screen.history.top) + [screen.buffer[y] for y in range(screen.lines)]
        while len(rows) > len(screen.history.top) + screen.cursor.y + 1 and not any(
                char.data.strip() for char in rows[-1].values()):
            rows.pop()
        result = Text()
        for row in rows:
            for attributes, chars in groupby((row[x] for x in range(screen.columns)), key=lambda char: char[1:]):
                chars = list(chars)
                char = chars[0]
                result.append(''.join(item.data for item in chars), Style(
                    color=self._color(char.fg), bgcolor=self._color(char.bg), bold=char.bold,
                    italic=char.italics, underline=char.underscore, reverse=char.reverse,
                    strike=char.strikethrough))
            result.append('\n')
        result.rstrip()
        return result

    @staticmethod
    def _color(color):
        if color == 'default':
            return None
        if re.fullmatch('[0-9a-fA-F]{6}', color):
            return '#' + color
        color = color.replace('brown', 'yellow')
        return 'bright_' + color[6:] if color.startswith('bright') else color
