from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Input, Label


class MultiCastCommand(Message):
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__()


class MultiCastPanel(Widget):
    visible = var(False)

    DEFAULT_CSS = """
    MultiCastPanel {
        dock: bottom;
        height: 5;
        display: none;
        border-top: solid $warning;
    }
    MultiCastPanel.-visible {
        display: block;
    }
    #multicast-warning {
        width: 100%;
        text-style: bold;
        color: $warning;
        padding: 0 1;
    }
    #multicast-input {
        margin: 0 1;
    }
    """

    def compose(self):
        yield Label(
            "Warning: Command will be sent to ALL connected servers",
            id="multicast-warning",
        )
        yield Input(placeholder="Type command and press Enter...", id="multicast-input")

    def watch_visible(self, visible: bool) -> None:
        self.set_class(visible, "-visible")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            self.post_message(MultiCastCommand(cmd))
        event.input.value = ""

    def show_panel(self) -> None:
        self.visible = True
        inp = self.query_one("#multicast-input", Input)
        inp.focus()

    def hide_panel(self) -> None:
        self.visible = False
