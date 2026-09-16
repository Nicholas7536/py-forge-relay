"""
Main entrypoint for the Minecraft-Discord Asynchronous Chat-Relay Pipeline.
Coordinates the Discord client, thread-isolated RCON, and WebSocket server.
"""

import asyncio
import logging
import signal
import sys

from config import Config
from discord_bot import RelayBot
from rcon_client import ThreadIsolatedRcon
from ws_server import GameEventServer

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("RelayPipeline")


async def main() -> None:
    # 1. Load & validate environment configuration
    try:
        config = Config.load()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # 2. Initialize thread-isolated RCON client
    rcon = ThreadIsolatedRcon(
        host=config.rcon_host,
        port=config.rcon_port,
        password=config.rcon_password,
        timeout=config.rcon_timeout,
    )

    # 3. Initialize Discord bot
    bot = RelayBot(
        channel_id=config.discord_channel_id,
        rcon_client=rcon,
    )

    # 4. Initialize WebSocket server for inbound Forge events
    ws_server = GameEventServer(
        host=config.ws_host,
        port=config.ws_port,
    )
    ws_server.set_event_handler(bot.handle_game_event)

    # 5. Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def request_shutdown():
        logger.info("Shutdown signal received. Initiating graceful teardown...")
        shutdown_event.set()

    # Register OS signals where supported
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            # Fallback for Windows environments where add_signal_handler is not implemented
            signal.signal(sig, lambda _s, _f: request_shutdown())

    # 6. Launch services concurrently
    logger.info("Starting WebSocket server and Discord Bot...")
    await ws_server.start()

    bot_task = asyncio.create_task(bot.start(config.discord_bot_token))
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    # Run until either Discord bot stops or shutdown is triggered
    done, pending = await asyncio.wait(
        [bot_task, shutdown_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # 7. Cleanup and teardown
    logger.info("Stopping services...")
    if not bot.is_closed():
        await bot.close()

    await ws_server.stop()
    await rcon.close()

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("Pipeline terminated cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
