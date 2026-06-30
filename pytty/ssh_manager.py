import asyncio
import asyncssh


class SSHManager:
    def __init__(self, host: str, port: int, user: str) -> None:
        self.host = host
        self.port = port
        self.user = user
        self._conn: asyncssh.SSHConnection | None = None
        self._process: asyncssh.SSHClientProcess | None = None
        self._closed = False

    async def connect(self) -> None:
        """Establish SSH connection and spawn a remote shell process."""
        self._conn = await asyncssh.connect(
            self.host,
            username=self.user,
            port=self.port,
            known_hosts=None,
            connect_timeout=10,
        )
        
        # Allocate a PTY and start the default shell session
        self._process = await self._conn.create_process(
            term_type="xterm-256color",
            term_size=(80, 24),
        )

    async def read_loop(self, callback) -> None:
        """Read output stream from the remote process and pass it to the callback."""
        if self._process is None:
            return
        
        callback("\n[dim]Shell session started[/]")
        
        while not self._closed:
            try:
                # Read incoming data from stdout stream
                data = await self._process.stdout.read(4096)
                if not data:
                    callback("\n[red]Session closed by remote host[/]")
                    break
                
                callback(data)
            except (asyncio.CancelledError, GeneratorExit):
                break
            except Exception as e:
                callback(f"\n[red]Session error: {type(e).__name__}: {e}[/]")
                break

    async def write(self, data: str) -> None:
        """Write string data directly to the remote stdin process."""
        if self._process and not self._process.is_closed():
            self._process.write(data)

    async def close(self) -> None:
        """Terminate the process and close the SSH transport connection."""
        self._closed = True
        if self._process:
            self._process.close()
        if self._conn:
            self._conn.close()
            try:
                await asyncio.wait_for(self._conn.wait_closed(), timeout=5)
            except Exception:
                pass

    @property
    def is_connected(self) -> bool:
        """Check if the connection is active."""
        return self._conn is not None and not self._conn.is_closed()