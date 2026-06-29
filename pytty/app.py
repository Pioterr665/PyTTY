import asyncio
import re

from textual.app import App
from textual.binding import Binding
from textual.widgets import Footer, TabbedContent, TabPane

from pytty.ssh_manager import SSHManager
from pytty.widgets.multicast_panel import MultiCastCommand, MultiCastPanel
from pytty.widgets.sidebar import ServerSelected, Sidebar
from pytty.widgets.tab_content import TabSessionClosed, ServerTabContent


class PyTTYApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 30;
        border-right: solid $primary;
    }

    #tab-content {
        width: 1fr;
    }

    MultiCastPanel {
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+g", "toggle_multicast", "Multi-Cast"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
    ]

    def __init__(self):
        super().__init__()
        self.active_connections: dict[str, SSHManager] = {}

    def compose(self):
        yield Sidebar(id="sidebar")
        yield TabbedContent(id="tab-content")
        yield Footer()
        yield MultiCastPanel()

    def action_toggle_multicast(self):
        panel = self.query_one(MultiCastPanel)
        if panel.visible:
            panel.hide_panel()
        else:
            panel.show_panel()

    def action_close_tab(self):
        tabs = self.query_one("#tab-content", TabbedContent)
        pane = tabs.active_pane
        if pane is not None and pane.id is not None:
            tabs.remove_pane(pane.id)

    def on_multi_cast_command(self, event: MultiCastCommand):
        self._distribute_multicast(event.command)

    def _distribute_multicast(self, command: str) -> None:
        for tab_id, ssh in list(self.active_connections.items()):
            if not ssh.is_connected:
                continue
            asyncio.create_task(ssh.write(command + "\r"))
            tab = self.query_one(f"#{tab_id}", ServerTabContent)
            tab.write_to_log(f"[yellow]--- Multicast: {command} ---[/]")

    def on_server_selected(self, event: ServerSelected):
        tabs = self.query_one("#tab-content", TabbedContent)
        tab_id = re.sub(r"[^a-zA-Z0-9_-]", "_", event.name)

        if tab_id not in {p.id for p in tabs.query(TabPane)}:
            content = ServerTabContent(event.name, event.host, event.user, event.port)
            content.tab_id = tab_id
            pane = TabPane(event.name, content, id=tab_id)
            tabs.add_pane(pane)
            self.active_connections[tab_id] = content.ssh

        tabs.active = tab_id

    def on_tab_session_closed(self, event: TabSessionClosed):
        if event.tab_id in self.active_connections:
            del self.active_connections[event.tab_id]

    async def action_quit(self):
        for ssh in self.active_connections.values():
            await ssh.close()
        self.active_connections.clear()
        await super().action_quit()
