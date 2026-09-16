"""
Asyncio WebSocket server that ingests real-time game events from the Minecraft Forge mod.
"""

import asyncio
import json
import logging
from typing import Callable, Awaitable, Dict, Any, Optional
import websockets
from websockets.server import WebSocketServerProtocol, serve

logger = logging.getLogger(__name__)

EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class GameEventServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._event_handler: Optional[EventHandler] = None
        self._server = None
        self._connected_clients = set()

    def set_event_handler(self, handler: EventHandler) -> None:
        """Registers the async callback to invoke when a game event arrives."""
        self._event_handler = handler

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Handles an incoming WebSocket connection from the Forge mod client."""
        client_address = websocket.remote_address
        logger.info(f"Forge mod connected from {client_address}")
        self._connected_clients.add(websocket)

        try:
            async for raw_message in websocket:
                try:
                    payload = json.loads(raw_message)
                    if self._event_handler:
                        await self._event_handler(payload)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from {client_address}: {raw_message}")
                except Exception as e:
                    logger.error(f"Error dispatching game event: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Forge mod disconnected from {client_address}")
        finally:
            self._connected_clients.discard(websocket)

    async def start(self) -> None:
        """Starts the WebSocket server."""
        self._server = await serve(self._handle_connection, self.host, self.port)
        logger.info(f"Game event WebSocket server listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stops the WebSocket server and disconnects active clients."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped.")
