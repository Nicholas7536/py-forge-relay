"""
Thread-isolated Minecraft RCON client.

TECHNICAL RATIONALE:
Standard RCON is a synchronous TCP protocol. When the Minecraft game server
experiences tick drops, garbage collection pauses, or network latency spikes,
socket reads can hang for multiple seconds.

In a pure asyncio loop, executing synchronous blocking socket calls freezes
the single thread of the event loop. This blocks discord.py from sending its
mandatory Gateway heartbeat (Opcode 1), resulting in connection drops (Error 1006).

This module uses `asyncio.to_thread` to isolate all blocking RCON socket I/O
into Python's worker thread pool, ensuring zero jitter on connection heartbeats.
"""

import asyncio
import json
import logging
import threading
from typing import Optional
from mcrcon import MCRcon, MCRconException

logger = logging.getLogger(__name__)


class ThreadIsolatedRcon:
    def __init__(self, host: str, port: int, password: str, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout

        self._rcon: Optional[MCRcon] = None
        self._lock = threading.Lock()  # Protects RCON socket across worker threads

    def _sync_connect(self) -> None:
        """Synchronously establishes or re-establishes an RCON connection."""
        if self._rcon is not None:
            try:
                self._rcon.disconnect()
            except Exception:
                pass
            self._rcon = None

        rcon = MCRcon(self.host, self.password, port=self.port, timeout=int(self.timeout))
        rcon.connect()
        self._rcon = rcon
        logger.info(f"Connected to Minecraft RCON at {self.host}:{self.port}")

    def _sync_command(self, command: str) -> str:
        """Blocking worker-thread command execution with retry/reconnect."""
        with self._lock:
            try:
                if self._rcon is None:
                    self._sync_connect()
                assert self._rcon is not None
                return self._rcon.command(command)
            except (MCRconException, OSError, AssertionError) as e:
                logger.warning(f"RCON connection error ({e}). Attempting reconnect...")
                try:
                    self._sync_connect()
                    assert self._rcon is not None
                    return self._rcon.command(command)
                except Exception as reconnect_err:
                    logger.error(f"Failed to execute RCON command after reconnect: {reconnect_err}")
                    return ""

    def _sync_disconnect(self) -> None:
        """Closes the underlying RCON socket cleanly."""
        with self._lock:
            if self._rcon is not None:
                try:
                    self._rcon.disconnect()
                except Exception:
                    pass
                self._rcon = None

    async def execute_command(self, command: str) -> str:
        """
        Executes an RCON command asynchronously using a thread pool.
        The main event loop remains fully responsive while the worker thread handles socket I/O.
        """
        return await asyncio.to_thread(self._sync_command, command)

    async def broadcast_chat(self, sender: str, message: str) -> bool:
        """
        Formats and broadcasts a Discord message into Minecraft chat via /tellraw.
        Renders as: [Discord] <Sender> message
        """
        # Clean special escape sequences to prevent Minecraft tellraw injection
        clean_sender = sender.replace('"', '\\"').replace("\n", " ")
        clean_msg = message.replace('"', '\\"').replace("\n", " ")

        payload = [
            {"text": "[Discord] ", "color": "blue", "bold": True},
            {"text": f"<{clean_sender}> ", "color": "white", "bold": False},
            {"text": clean_msg, "color": "gray", "bold": False}
        ]

        tellraw_cmd = f'tellraw @a {json.dumps(payload)}'
        response = await self.execute_command(tellraw_cmd)
        return response is not None

    async def close(self) -> None:
        """Gracefully disconnects RCON off the main thread."""
        await asyncio.to_thread(self._sync_disconnect)
