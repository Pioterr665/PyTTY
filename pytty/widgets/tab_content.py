import asyncio

import asyncssh
from rich.text import Text
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Static

from pytty.ssh_manager import SSHManager
from pytty.widgets.log_highlighter import LogHighlighter


class TabSessionClosed(Message):
    def __init__(self, tab_id: str) -> None:
        self.tab_id = tab_id
        super().__init__()


class ServerTabContent(Widget):
    DEFAULT_CSS = """
    ServerTabContent {
        layout: vertical;
        height: 1fr;
    }
    #session-log {
        height: 1fr;
        min-height: 10;
    }
    #command-input {
        height: 3;
        dock: bottom;
    }
    """

    def __init__(self, name: str, host: str, user: str, port: int = 22) -> None:
        super().__init__()
        self.server_name = name
        self.host = host
        self.user = user
        self.port = port
        self.ssh = SSHManager(host, port, user)
        self.highlighter = LogHighlighter()
        self.tab_id: str | None = None
        self._log_lines: list[str] = []

    def compose(self):
        with VerticalScroll(id="session-log"):
            yield Static(id="log-output", markup=True)
        yield Input(id="command-input", placeholder="Type command and press Enter...")

    def on_mount(self):
        self.log_scroll = self.query_one("#session-log", VerticalScroll)
        self.log_output = self.query_one("#log-output", Static)
        self.inp = self.query_one("#command-input", Input)
        self.inp.disabled = True
        self._append_log(f"[bold]Connecting to {self.user}@{self.host}:{self.port}...[/]")
        self.run_worker(self._ssh_task(), name=f"ssh-{id(self)}", exclusive=True, exit_on_error=False)

    def _append_log(self, text: str) -> None:
        self._log_lines.append(text)
        self.log_output.update("\n".join(self._log_lines))
        self.log_scroll.scroll_end(animate=False)

    async def _ssh_task(self):
        try:
            self._append_log("[bold]Establishing SSH transport...[/]")
            connect_task = asyncio.create_task(self.ssh.connect())
            for attempt in range(1, 6):
                done, _ = await asyncio.wait([connect_task], timeout=1)
                if done:
                    break
                self._append_log(f"[dim]Waiting for {self.user}@{self.host}:{self.port} ({attempt}s)...[/]")
            await connect_task
            self.inp.disabled = False
            self.inp.focus()
            self._append_log(f"[bold green]Connected to {self.server_name}[/]")
            asyncio.create_task(self.ssh.write("\r"))
            await self.ssh.read_loop(self._on_ssh_output)
        except asyncio.CancelledError:
            pass
        except TimeoutError:
            self._append_log(
                f"[bold red]Connection to {self.user}@{self.host}:{self.port} TIMED OUT[/]"
            )
            self._append_log(
                "[dim]Host did not respond within 10s. Check IP/port and network connectivity.[/]"
            )
            self._append_log(
                "[dim]TIP: Try 'ping' to check if host is reachable.[/]"
            )
        except OSError as e:
            self._append_log(
                f"[bold red]Cannot reach {self.user}@{self.host}:{self.port}[/]"
            )
            self._append_log(f"[red]OS Error ({type(e).__name__}): {e}[/]")
            self._append_log(
                "[dim]TIP: Check if SSH agent is running (ssh-add -l) and host is correct.[/]"
            )
        except ConnectionError as e:
            self._append_log(
                f"[bold red]Connection refused by {self.user}@{self.host}:{self.port}[/]"
            )
            self._append_log(f"[red]{type(e).__name__}: {e}[/]")
            self._append_log(
                "[dim]TIP: Make sure SSH server is running and key is loaded (ssh-add -l).[/]"
            )
        except asyncssh.PermissionDenied as e:
            self._append_log(
                f"[bold yellow]Authentication failed for {self.user}@{self.host}:{self.port}[/]"
            )
            self._append_log(f"[red]{e}[/]")
            self._append_log(
                "[dim]TIP: Run 'ssh-add -l' to check loaded keys, "
                "'ssh-keygen' to create a new key, "
                "or 'ssh-copy-id {user}@{host}' to install your key on the server.[/]"
            )
        except Exception as e:
            self._append_log(
                f"[bold red]Connection to {self.user}@{self.host}:{self.port} FAILED[/]"
            )
            self._append_log(f"[red]{type(e).__name__}: {e}[/]")
            self._append_log(
                "[dim]TIP: Verify connection details (IP, port, username) and network.[/]"
            )
        finally:
            self.inp.disabled = True
            await self.ssh.close()

    def _on_ssh_output(self, data: str) -> None:
        for line in data.rstrip("\n").split("\n"):
            highlighted = self.highlighter.highlight(line)
            if isinstance(highlighted, Text):
                self._append_log(highlighted.markup)
            else:
                self._append_log(str(highlighted))

    def write_to_log(self, text: str) -> None:
        self._append_log(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd and self.ssh.is_connected:
            self._append_log(f"[bold dim]{self.server_name}[/][bold]$ {cmd}[/]")
            asyncio.create_task(self.ssh.write(cmd + "\r"))
        event.input.value = ""

    def on_unmount(self):
        asyncio.create_task(self.ssh.close())
        if self.tab_id is not None:
            self.post_message(TabSessionClosed(self.tab_id))
