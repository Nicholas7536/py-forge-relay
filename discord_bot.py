"""
Discord Bot client managing the bi-directional chat relay with Minecraft.
"""

import logging
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

from rcon_client import ThreadIsolatedRcon

logger = logging.getLogger(__name__)


class RelayBot(commands.Bot):
    def __init__(self, channel_id: int, rcon_client: ThreadIsolatedRcon):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)
        self.relay_channel_id = channel_id
        self.rcon_client = rcon_client
        self._target_channel: Optional[discord.TextChannel] = None

    async def on_ready(self) -> None:
        """Called when Discord bot has established a connection and is ready."""
        logger.info(f"Discord Bot logged in as {self.user} (ID: {self.user.id})")
        channel = self.get_channel(self.relay_channel_id)

        if channel is None:
            try:
                channel = await self.fetch_channel(self.relay_channel_id)
            except Exception as e:
                logger.error(f"Could not find or fetch Discord channel ID {self.relay_channel_id}: {e}")
                return

        if isinstance(channel, discord.TextChannel):
            self._target_channel = channel
            logger.info(f"Relay channel active: #{channel.name} (ID: {channel.id})")
            # Set bot presence
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="Minecraft Chat Relay"
                )
            )
        else:
            logger.error(f"Channel {self.relay_channel_id} is not a valid text channel.")

    async def on_message(self, message: discord.Message) -> None:
        """
        Intercepts messages in the designated Discord channel and relays them
        to Minecraft via thread-isolated RCON.
        """
        # Ignore messages sent by any bot (including ourselves)
        if message.author.bot:
            return

        # Ensure message is in the designated relay channel
        if message.channel.id != self.relay_channel_id:
            return

        clean_text = message.clean_content.strip()
        if not clean_text:
            return

        author_name = message.author.display_name
        logger.info(f"[Discord -> MC] <{author_name}> {clean_text}")

        # Send to Minecraft via thread-isolated RCON
        success = await self.rcon_client.broadcast_chat(author_name, clean_text)
        if not success:
            logger.warning("Failed to broadcast Discord message to Minecraft.")

    async def handle_game_event(self, event: Dict[str, Any]) -> None:
        """
        Receives game events from the WebSocket server and sends them to Discord.
        """
        if self._target_channel is None:
            logger.warning("Target Discord channel not available yet. Dropping game event.")
            return

        event_type = (event.get("event") or event.get("type") or "").lower()
        player = event.get("player") or event.get("username") or "Unknown"

        try:
            if event_type == "chat":
                msg = event.get("message", "")
                if msg:
                    safe_msg = discord.utils.escape_markdown(msg)
                    safe_player = discord.utils.escape_markdown(player)
                    await self._target_channel.send(f"**<{safe_player}>** {safe_msg}")

            elif event_type == "join":
                safe_player = discord.utils.escape_markdown(player)
                await self._target_channel.send(f"**{safe_player}** joined the server")

            elif event_type in ("leave", "quit"):
                safe_player = discord.utils.escape_markdown(player)
                await self._target_channel.send(f"**{safe_player}** left the server")

            elif event_type == "death":
                death_message = event.get("message") or f"{player} died"
                safe_death = discord.utils.escape_markdown(death_message)
                await self._target_channel.send(f"*{safe_death}*")

            elif event_type == "status":
                online_count = event.get("online", "?")
                max_count = event.get("max", "?")
                tps = event.get("tps", "20.0")
                await self._target_channel.send(
                    f"[Server Status] {online_count}/{max_count} players online | TPS: {tps}"
                )

            else:
                logger.debug(f"Unhandled game event type: {event_type} - {event}")

        except Exception as e:
            logger.error(f"Failed to post game event to Discord: {e}")
