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
    """Sent when an SSH session tab is closed."""
    def __init__(self, tab_id: str) -> None:
        self.tab_id = tab_id
        super().__init__()


class ServerTabContent(Widget):
    """Widget managing an individual SSH session terminal interface."""
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
        self.text_buffer = Text()

    def compose(self):
        with VerticalScroll(id="session-log"):
            yield Static(id="log-output")
        yield Input(id="command-input", placeholder="Type command and press Enter...")

    def on_mount(self):
        self.log_scroll = self.query_one("#session-log", VerticalScroll)
        self.log_output = self.query_one("#log-output", Static)
        self.inp = self.query_one("#command-input", Input)
        self.inp.disabled = True
        self._append_log(f"[bold]Connecting to {self.user}@{self.host}:{self.port}...[/]")
        self.run_worker(self._ssh_task(), name=f"ssh-{id(self)}", exclusive=True, exit_on_error=False)

    def _append_log(self, text: str | Text) -> None:
        """Appends plain markup string or a rich Text object to the terminal buffer."""
        if isinstance(text, str):
            self.text_buffer.append(Text.from_markup(text + "\n"))
        else:
            self.text_buffer.append(text)
        
        self.log_output.update(self.text_buffer)
        self.log_scroll.scroll_end(animate=False)

    async def _ssh_task(self):
        """Worker task handling the SSH connection lifecycle."""
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
            
            # Send initial return to trigger the first prompt display
            asyncio.create_task(self.ssh.write("\r"))
            await self.ssh.read_loop(self._on_ssh_output)
        except asyncio.CancelledError:
            pass
        except TimeoutError:
            self._append_log(f"[bold red]Connection to {self.user}@{self.host}:{self.port} TIMED OUT[/]")
        except OSError as e:
            self._append_log(f"[bold red]Cannot reach {self.user}@{self.host}:{self.port}[/]")
            self._append_log(f"[red]OS Error ({type(e).__name__}): {e}[/]")
        except ConnectionError as e:
            self._append_log(f"[bold red]Connection refused by {self.user}@{self.host}:{self.port}[/]")
        except asyncssh.PermissionDenied as e:
            self._append_log(f"[bold yellow]Authentication failed for {self.user}@{self.host}:{self.port}[/]")
            self._append_log(f"[red]{e}[/]")
        except Exception as e:
            self._append_log(f"[bold red]Connection to {self.user}@{self.host}:{self.port} FAILED[/]")
            self._append_log(f"[red]{type(e).__name__}: {e}[/]")
        finally:
            self.inp.disabled = True
            await self.ssh.close()

    def _on_ssh_output(self, data: str) -> None:
        """Handles and formats raw incoming data chunks from the SSH session."""
        # FIX: Interpret raw ANSI/VT100 escape codes (colors, weights) into Rich styles
        ansi_interpreted_text = Text.from_ansi(data)
        self._append_log(ansi_interpreted_text)

    def write_to_log(self, text: str) -> None:
        """Writes a system log entry."""
        self._append_log(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Sends user commands to the SSH backend upon submission."""
        cmd = event.value
        
        if self.ssh.is_connected:
            # FIX: We don't log the command manually anymore. 
            # The remote PTY will echo it back naturally along with the execution results.
            asyncio.create_task(self.ssh.write(cmd + "\r"))
            
        event.input.value = ""

    def on_unmount(self):
        """Cleans up the SSH connection when the widget is unmounted."""
        asyncio.create_task(self.ssh.close())
        if self.tab_id is not None:
            self.post_message(TabSessionClosed(self.tab_id))