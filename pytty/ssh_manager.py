import asyncio

import asyncssh


class _OutputCollector(asyncssh.SSHClientSession):
    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self.queue = queue

    def session_started(self) -> None:
        self.queue.put_nowait(("session_started", None))

    def data_received(self, data: bytes, datatype: int) -> None:
        self.queue.put_nowait(("data", data.decode("utf-8", errors="replace")))

    def connection_lost(self, exc: Exception | None) -> None:
        self.queue.put_nowait(("closed", exc))


class SSHManager:
    def __init__(self, host: str, port: int, user: str) -> None:
        self.host = host
        self.port = port
        self.user = user
        self._conn: asyncssh.SSHConnection | None = None
        self._session: asyncssh.SSHSession | None = None
        self._client: _OutputCollector | None = None
        self._closed = False

    async def connect(self) -> None:
        self._conn = await asyncssh.connect(
            self.host,
            username=self.user,
            port=self.port,
            known_hosts=None,
            connect_timeout=10,
        )
        queue: asyncio.Queue = asyncio.Queue()
        self._session, self._client = await self._conn.create_session(
            lambda: _OutputCollector(queue),
            term_type="xterm-256color",
            term_size=(80, 24),
            request_pty=True,
            encoding=None,
        )

    async def read_loop(self, callback) -> None:
        if self._client is None:
            return
        while not self._closed:
            msg = await self._client.queue.get()
            kind, payload = msg[0], msg[1]
            if kind == "data":
                callback(payload)
            elif kind == "session_started":
                callback("\n[dim]Shell session started[/]")
            elif kind == "closed":
                if payload is not None:
                    callback(f"\n[red]Session closed: {payload}[/]")
                break

    async def write(self, data: str) -> None:
        if self._session and not self._session.is_closed():
            self._session.write(data.encode())

    async def close(self) -> None:
        self._closed = True
        if self._client:
            try:
                self._client.queue.put_nowait(("closed", None))
            except asyncio.QueueFull:
                pass
        if self._conn:
            self._conn.close()
            try:
                await asyncio.wait_for(self._conn.wait_closed(), timeout=5)
            except Exception:
                pass

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed()
