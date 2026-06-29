import re

from rich.style import Style
from rich.text import Text


class LogHighlighter:
    def __init__(self):
        self._rules = [
            (re.compile(r"\b(ERROR|CRITICAL|FAILED)\b", re.IGNORECASE),
             Style(color="red", bold=True)),
            (re.compile(r"\b(WARN(ING)?|ATTENTION)\b", re.IGNORECASE),
             Style(color="yellow")),
            (re.compile(r"\b(INFO|SUCCESS|OK)\b", re.IGNORECASE),
             Style(color="green")),
            (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
             Style(color="cyan")),
            (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
             Style(color="magenta")),
            (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
             Style(color="cyan")),
        ]

    def highlight(self, text: str) -> Text:
        t = Text.from_ansi(text)
        for pattern, style in self._rules:
            for match in pattern.finditer(t.plain):
                t.stylize(style, match.start(), match.end())
        return t
